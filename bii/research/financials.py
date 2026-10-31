"""Finanzkennzahlen aus SEC-XBRL (companyfacts) – reine Rechenregeln, keine KI.

Jeder Wert behält seine Herkunft: XBRL-Konzept, Einreichung (Accession), Formular, Einreichungsdatum.
Quartalswerte für Cashflows werden aus kumulierten Werten (3/6/9/12 Monate) hergeleitet und als
'abgeleitet' markiert. Ein Q4 ergibt sich aus Gesamtjahr minus neun Monate.
"""
from __future__ import annotations

from datetime import date

# Konzepte mit Ausweichkonzepten (erste vorhandene gewinnt; das benutzte Konzept wird gespeichert)
FLOW = {
    "umsatz": ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet"],
    "umsatzkosten": ["CostOfRevenue", "CostOfGoodsAndServicesSold"],
    "bruttogewinn": ["GrossProfit"],
    "fue": ["ResearchAndDevelopmentExpense"],
    "operatives_ergebnis": ["OperatingIncomeLoss"],
    "nettoergebnis": ["NetIncomeLoss"],
    "operativer_cashflow": ["NetCashProvidedByUsedInOperatingActivities"],
    "investitionen": ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"],
    "aktienverguetung": ["ShareBasedCompensation", "AllocatedShareBasedCompensationExpense"],
    "aktienrueckkauf": ["PaymentsForRepurchaseOfCommonStock"],
    "dividenden": ["PaymentsOfDividendsCommonStock", "PaymentsOfDividends"],
}
INSTANT = {
    "liquide_mittel": ["CashAndCashEquivalentsAtCarryingValue"],
    "kurzfristige_wertpapiere": ["MarketableSecuritiesCurrent", "ShortTermInvestments",
                                 "AvailableForSaleSecuritiesDebtSecuritiesCurrent"],
    "langfristige_schulden": ["LongTermDebtNoncurrent", "LongTermDebt"],
    "kurzfristige_schulden": ["LongTermDebtCurrent", "DebtCurrent", "ShortTermBorrowings"],
    "eigenkapital": ["StockholdersEquity"],
    "vorraete": ["InventoryNet"],
}


def _d(s: str) -> date:
    return date.fromisoformat(s)


def _units(facts: dict, concept: str, taxonomy: str = "us-gaap") -> list[dict]:
    c = facts.get("facts", {}).get(taxonomy, {}).get(concept)
    if not c:
        return []
    units = c.get("units", {})
    return units.get("USD") or units.get("shares") or units.get("USD/shares") or next(iter(units.values()), [])


def _latest_filed(rows: list[dict]) -> dict:
    """Pro Zeitraum gilt der zuletzt eingereichte Wert (erfasst Korrekturen in späteren Berichten)."""
    best: dict = {}
    for r in rows:
        if r.get("form") not in ("10-K", "10-Q", "10-K/A", "10-Q/A"):
            continue
        key = (r.get("start"), r["end"])
        if key not in best or r["filed"] > best[key]["filed"]:
            best[key] = r
    return best


def restatements(facts: dict, concept: str) -> list[dict]:
    """Zeiträume, deren Wert in einer späteren Einreichung um >0,5 % geändert wurde."""
    by: dict = {}
    for r in _units(facts, concept):
        if r.get("form") in ("10-K", "10-Q", "10-K/A", "10-Q/A"):
            by.setdefault((r.get("start"), r["end"]), []).append(r)
    out = []
    for (s, e), rows in by.items():
        vals = sorted(rows, key=lambda r: r["filed"])
        first, last = vals[0], vals[-1]
        if first["val"] and abs(last["val"] / first["val"] - 1) > 0.005:
            out.append({"konzept": concept, "start": s, "ende": e, "alt": first["val"], "neu": last["val"],
                        "alt_accn": first["accn"], "neu_accn": last["accn"], "neu_eingereicht": last["filed"]})
    return out


def flow_series(facts: dict, names: list[str]) -> tuple[str | None, list[dict]]:
    """Quartalswerte (3 Monate) für eine Bewegungsgröße, inkl. hergeleiteter Quartale.

    Je Geschäftsjahr werden die Quartalsenden chronologisch durchlaufen und eine kumulierte Summe geführt:
    - gibt es einen direkten 3-Monats-Wert, wird er verwendet;
    - sonst Quartal = kumulierter Wert (Beginn = Geschäftsjahresbeginn) − kumulierte Summe bis zum Vorquartal.
    So entstehen Q2/Q3 aus 6-/9-Monatswerten (Cashflows) und Q4 aus Jahreswert − neun Monate.
    """
    for concept in names:
        rows = _latest_filed(_units(facts, concept))
        if not rows:
            continue
        dur = {k: v for k, v in rows.items() if k[0]}
        length = {k: (_d(k[1]) - _d(k[0])).days for k in dur}
        direct = {e: (s, r) for (s, e), r in dur.items() if 80 <= length[(s, e)] <= 100}
        # Geschäftsjahresbeginne: Beginn von Jahreswerten und von kumulierten 6-/9-Monatswerten
        fy_starts = sorted({s for (s, e), n in length.items() if 170 <= n <= 290 or 350 <= n <= 380})
        quarters: dict = {}
        for e, (s, r) in direct.items():
            quarters[e] = {"start": s, "ende": e, "wert": r["val"], "accn": r["accn"], "form": r["form"],
                           "eingereicht": r["filed"], "abgeleitet": False}
        for fs in fy_starts:
            cum = {e: r for (s, e), r in dur.items() if s == fs and 80 <= length[(s, e)] <= 380}
            ends = sorted(set(cum) | {e for e, (s, _) in direct.items() if s >= fs and (_d(e) - _d(fs)).days <= 380})
            running, prev_end = 0.0, fs
            for e in ends:
                if e in direct and direct[e][0] >= prev_end:
                    q = direct[e][1]["val"]
                elif e in cum and running is not None:
                    q = cum[e]["val"] - running
                    if e not in quarters:
                        r = cum[e]
                        quarters[e] = {"start": prev_end, "ende": e, "wert": q, "accn": r["accn"], "form": r["form"],
                                       "eingereicht": r["filed"], "abgeleitet": True}
                else:
                    running = None      # Lücke – keine weitere Herleitung in diesem Geschäftsjahr
                    continue
                running = cum[e]["val"] if e in cum else (running + q if running is not None else None)
                prev_end = e
        q = sorted(quarters.values(), key=lambda x: x["ende"])
        if q:
            return concept, q
    return None, []


def instant_series(facts: dict, names: list[str]) -> tuple[str | None, list[dict]]:
    for concept in names:
        rows = _latest_filed(_units(facts, concept))
        pts = sorted(({"ende": e, "wert": r["val"], "accn": r["accn"], "form": r["form"], "eingereicht": r["filed"]}
                      for (s, e), r in rows.items() if not s), key=lambda x: x["ende"])
        if pts:
            return concept, pts
    return None, []


def shares_outstanding(facts: dict) -> dict | None:
    rows = _units(facts, "EntityCommonStockSharesOutstanding", "dei")
    if not rows:
        return None
    r = max(rows, key=lambda r: (r["end"], r["filed"]))
    return {"ende": r["end"], "wert": r["val"], "accn": r["accn"], "form": r.get("form"), "eingereicht": r["filed"]}


def build(facts: dict) -> dict:
    """Kompaktes, quellenbelegtes Finanzprofil."""
    out = {"quelle": facts.get("_meta", {}), "flow": {}, "instant": {}, "konzepte": {}}
    for k, names in FLOW.items():
        c, q = flow_series(facts, names)
        out["flow"][k] = q[-12:]
        out["konzepte"][k] = c
    for k, names in INSTANT.items():
        c, p = instant_series(facts, names)
        out["instant"][k] = p[-6:]
        out["konzepte"][k] = c
    out["aktien_ausstehend"] = shares_outstanding(facts)
    out["korrekturen"] = []
    for k in ("umsatz", "nettoergebnis", "operatives_ergebnis"):
        c = out["konzepte"].get(k)
        if c:
            out["korrekturen"] += restatements(facts, c)
    out["kennzahlen"] = metrics(out)
    return out


def _by_end(q: list[dict]) -> dict:
    return {x["ende"]: x for x in q}


def _yoy(q: list[dict], end: str) -> float | None:
    m = _by_end(q)
    if end not in m:
        return None
    e = _d(end)
    for k, v in m.items():
        if 350 <= (e - _d(k)).days <= 380 and v["wert"]:
            return m[end]["wert"] / v["wert"] - 1
    return None


def metrics(fin: dict) -> dict:
    f = fin["flow"]
    rev = f.get("umsatz", [])
    if not rev:
        return {}
    last = rev[-1]["ende"]
    k: dict = {"letztes_quartal": last}

    def q(name, end=last):
        return _by_end(f.get(name, [])).get(end, {}).get("wert")

    def ttm(name):
        series = f.get(name, [])
        ends = [x["ende"] for x in series]
        if last not in ends:
            return None
        i = ends.index(last)
        window = series[max(0, i - 3): i + 1]
        if len(window) < 4 or (_d(window[-1]["ende"]) - _d(window[0]["ende"])).days > 290:
            return None
        return sum(x["wert"] for x in window)

    r = q("umsatz")
    gp = q("bruttogewinn") if q("bruttogewinn") is not None else (r - q("umsatzkosten") if r and q("umsatzkosten") is not None else None)
    k["umsatz_q"] = r
    k["umsatzwachstum_yoy_q"] = _yoy(rev, last)
    k["umsatzwachstum_yoy_hist"] = [{"ende": x["ende"], "wachstum": _yoy(rev, x["ende"])} for x in rev[-8:]]
    k["bruttomarge_q"] = gp / r if gp is not None and r else None
    gm_hist = []
    for x in rev[-8:]:
        g = q("bruttogewinn", x["ende"])
        if g is None and q("umsatzkosten", x["ende"]) is not None:
            g = x["wert"] - q("umsatzkosten", x["ende"])
        gm_hist.append({"ende": x["ende"], "marge": (g / x["wert"]) if g is not None and x["wert"] else None})
    k["bruttomarge_hist"] = gm_hist
    oi = q("operatives_ergebnis")
    k["operative_marge_q"] = oi / r if oi is not None and r else None
    for name in ("umsatz", "nettoergebnis", "operativer_cashflow", "investitionen", "operatives_ergebnis",
                 "aktienverguetung", "aktienrueckkauf", "dividenden", "fue"):
        k[f"{name}_ttm"] = ttm(name)
    if k["operativer_cashflow_ttm"] is not None and k["investitionen_ttm"] is not None:
        k["fcf_ttm"] = k["operativer_cashflow_ttm"] - k["investitionen_ttm"]
        k["fcf_marge_ttm"] = k["fcf_ttm"] / k["umsatz_ttm"] if k["umsatz_ttm"] else None
    inst = fin["instant"]

    def latest(name):
        p = inst.get(name) or []
        return p[-1]["wert"] if p else 0.0

    cash = latest("liquide_mittel") + latest("kurzfristige_wertpapiere")
    debt = latest("langfristige_schulden") + latest("kurzfristige_schulden")
    k["liquiditaet"] = cash
    k["finanzschulden"] = debt
    k["nettoliquiditaet"] = cash - debt
    return k
