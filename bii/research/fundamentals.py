"""Finanzkennzahlen aus SEC-XBRL-'companyfacts' (offizielle, maschinenlesbare Abschlussdaten).

Jeder Wert trägt seine Quelle: Konzept, Zeitraum, Formular, Einreichungsdatum, Accession-Nummer.
Quartalswerte werden aus 3-Monats-Fakten oder aus Differenzen kumulierter Werte (YTD) abgeleitet.
Abgeleitete Werte sind als solche markiert (z. B. Q4 = Geschäftsjahr minus 9 Monate).
"""
from __future__ import annotations

from datetime import date

# Konzepte in Prioritätsreihenfolge (Unternehmen nutzen unterschiedliche US-GAAP-Elemente)
FLOW = {
    "umsatz": ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet",
               "RevenueFromContractWithCustomerIncludingAssessedTax"],
    "herstellkosten": ["CostOfRevenue", "CostOfGoodsAndServicesSold"],
    "bruttogewinn": ["GrossProfit"],
    "forschung_entwicklung": ["ResearchAndDevelopmentExpense",
                              "ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost"],
    "operatives_ergebnis": ["OperatingIncomeLoss"],
    "nettoergebnis": ["NetIncomeLoss"],
    "operativer_cashflow": ["NetCashProvidedByUsedInOperatingActivities"],
    "investitionen_sachanlagen": ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"],
    "aktienverguetung": ["ShareBasedCompensation", "AllocatedShareBasedCompensationExpense"],
    "aktienrueckkaeufe": ["PaymentsForRepurchaseOfCommonStock"],
    "dividenden": ["PaymentsOfDividends", "PaymentsOfDividendsCommonStock"],
}
INSTANT = {
    "liquide_mittel": ["CashAndCashEquivalentsAtCarryingValue"],
    "wertpapiere_kurzfristig": ["MarketableSecuritiesCurrent", "AvailableForSaleSecuritiesDebtSecuritiesCurrent",
                                "ShortTermInvestments"],
    "finanzschulden_langfristig": ["LongTermDebtNoncurrent", "LongTermDebt"],
    "finanzschulden_kurzfristig": ["LongTermDebtCurrent", "DebtCurrent"],
    "eigenkapital": ["StockholdersEquity"],
    "bilanzsumme": ["Assets"],
    "vorraete": ["InventoryNet"],
}
SHARES = ["EntityCommonStockSharesOutstanding"]   # dei
DIL_SHARES = ["WeightedAverageNumberOfDilutedSharesOutstanding"]
ANNUAL_FORMS = {"10-K", "10-K/A", "20-F", "40-F"}
QUARTER_FORMS = {"10-Q", "10-Q/A"}


def _d(s: str) -> date:
    return date.fromisoformat(s)


def _days(f: dict) -> int:
    return (_d(f["end"]) - _d(f["start"])).days


def _facts(cf: dict, concepts: list[str], taxonomy: str = "us-gaap", unit: str = "USD") -> tuple[str | None, list[dict]]:
    tax = cf.get("facts", {}).get(taxonomy, {})
    best = None
    for c in concepts:
        if c in tax and unit in tax[c].get("units", {}):
            facts = [f for f in tax[c]["units"][unit] if f.get("form") in ANNUAL_FORMS | QUARTER_FORMS]
            if facts:
                latest = max(f["end"] for f in facts)
                # Konzept mit den aktuellsten Daten bevorzugen (Firmen wechseln Elemente über die Zeit)
                if best is None or latest > best[2]:
                    best = (c, facts, latest)
    return (best[0], best[1]) if best else (None, [])


def _dedupe(facts: list[dict], key) -> dict:
    """Je Schlüssel den zuletzt eingereichten Wert behalten (Korrekturen/Restatements)."""
    out = {}
    for f in facts:
        k = key(f)
        if k not in out or f["filed"] > out[k]["filed"]:
            out[k] = f
    return out


def _src(f: dict, concept: str, derived: str | None = None) -> dict:
    s = {"konzept": concept, "von": f.get("start"), "bis": f["end"], "formular": f.get("form"),
         "eingereicht": f.get("filed"), "accession": f.get("accn")}
    if derived:
        s["abgeleitet"] = derived
    return s


def quarterly(cf: dict, concepts: list[str]) -> list[dict]:
    """Quartalswerte (ca. 3 Monate) mit Quelle, ältestes zuerst."""
    concept, facts = _facts(cf, concepts)
    if not facts:
        return []
    durs = [f for f in facts if f.get("start")]
    by_period = _dedupe(durs, lambda f: (f["start"], f["end"]))
    q: dict[str, dict] = {}
    for f in by_period.values():
        if 80 <= _days(f) <= 100:
            q[f["end"]] = {"ende": f["end"], "wert": f["val"], "quelle": _src(f, concept)}
    # Ableitung aus kumulierten Werten mit gleichem Startdatum (YTD: 6M-3M, 9M-6M, 12M-9M)
    groups: dict[str, list[dict]] = {}
    for f in by_period.values():
        groups.setdefault(f["start"], []).append(f)
    for start, fs in groups.items():
        fs.sort(key=lambda f: f["end"])
        for a, b in zip(fs, fs[1:]):
            if 80 <= (_d(b["end"]) - _d(a["end"])).days <= 100 and b["end"] not in q:
                q[b["end"]] = {"ende": b["end"], "wert": b["val"] - a["val"],
                               "quelle": _src(b, concept, f"{b['end']} kumuliert minus {a['end']} kumuliert")}
    # Fallback für Q4: Geschäftsjahr minus Summe der drei vorherigen Quartale desselben Jahres
    for f in by_period.values():
        if 350 <= _days(f) <= 380 and f["end"] not in q:
            inner = [q[k] for k in sorted(q) if f["start"] < k < f["end"]]
            if len(inner) == 3:
                q[f["end"]] = {"ende": f["end"], "wert": f["val"] - sum(x["wert"] for x in inner),
                               "quelle": _src(f, concept, "Geschäftsjahr minus Summe Q1–Q3")}
    return [q[k] for k in sorted(q)]


def annual(cf: dict, concepts: list[str]) -> list[dict]:
    concept, facts = _facts(cf, concepts)
    fy = [f for f in facts if f.get("start") and 350 <= _days(f) <= 380 and f.get("form") in ANNUAL_FORMS]
    by = _dedupe(fy, lambda f: f["end"])
    return [{"ende": k, "wert": by[k]["val"], "quelle": _src(by[k], concept)} for k in sorted(by)]


def instant(cf: dict, concepts: list[str], taxonomy="us-gaap", unit="USD") -> dict | None:
    concept, facts = _facts(cf, concepts, taxonomy, unit)
    if not facts:
        return None
    f = max(facts, key=lambda f: (f["end"], f["filed"]))
    return {"stichtag": f["end"], "wert": f["val"], "quelle": _src(f, concept)}


def ttm(qs: list[dict]) -> dict | None:
    """Summe der letzten 4 lückenlos aufeinanderfolgenden Quartale."""
    if len(qs) < 4:
        return None
    last4 = qs[-4:]
    for a, b in zip(last4, last4[1:]):
        if not 80 <= (_d(b["ende"]) - _d(a["ende"])).days <= 100:
            return None
    return {"bis": last4[-1]["ende"], "wert": sum(x["wert"] for x in last4),
            "quartale": [x["ende"] for x in last4], "quellen": [x["quelle"] for x in last4]}


def profile(cf: dict) -> dict:
    """Kennzahlenprofil: Quartale, TTM, Geschäftsjahre, Bilanz, abgeleitete Kennzahlen."""
    out = {"quartale": {}, "ttm": {}, "geschaeftsjahre": {}, "bilanz": {}, "kennzahlen": {}}
    for k, cs in FLOW.items():
        qs = quarterly(cf, cs)
        out["quartale"][k] = qs[-8:]
        t = ttm(qs)
        if t:
            out["ttm"][k] = t
        out["geschaeftsjahre"][k] = annual(cf, cs)[-4:]
    # Bruttogewinn notfalls aus Umsatz - Herstellkosten
    if "bruttogewinn" not in out["ttm"] and {"umsatz", "herstellkosten"} <= out["ttm"].keys():
        out["ttm"]["bruttogewinn"] = {"bis": out["ttm"]["umsatz"]["bis"],
                                      "wert": out["ttm"]["umsatz"]["wert"] - out["ttm"]["herstellkosten"]["wert"],
                                      "abgeleitet": "Umsatz minus Herstellkosten"}
    for k, cs in INSTANT.items():
        v = instant(cf, cs)
        if v:
            out["bilanz"][k] = v
    sh = instant(cf, SHARES, taxonomy="dei", unit="shares")
    if sh:
        out["bilanz"]["aktien_ausstehend"] = sh
    out["kennzahlen"] = derived_metrics(out)
    return out


def _v(d: dict, k: str):
    return d[k]["wert"] if k in d else None


def derived_metrics(p: dict) -> dict:
    t, b = p["ttm"], p["bilanz"]
    m = {}
    rev = _v(t, "umsatz")
    if rev:
        for name, k in (("bruttomarge", "bruttogewinn"), ("operative_marge", "operatives_ergebnis"),
                        ("nettomarge", "nettoergebnis"), ("fue_quote", "forschung_entwicklung")):
            if _v(t, k) is not None:
                m[name] = _v(t, k) / rev
    cfo, capex = _v(t, "operativer_cashflow"), _v(t, "investitionen_sachanlagen")
    if cfo is not None and capex is not None:
        m["free_cashflow"] = cfo - capex
        if rev:
            m["fcf_marge"] = (cfo - capex) / rev
            m["capex_quote"] = capex / rev
        sbc = _v(t, "aktienverguetung")
        if sbc is not None:
            m["free_cashflow_nach_sbc"] = cfo - capex - sbc
    cash = (_v(b, "liquide_mittel") or 0) + (_v(b, "wertpapiere_kurzfristig") or 0)
    debt = (_v(b, "finanzschulden_langfristig") or 0) + (_v(b, "finanzschulden_kurzfristig") or 0)
    if "liquide_mittel" in b:
        m["liquiditaet"] = cash
        m["finanzschulden"] = debt
        m["nettoliquiditaet"] = cash - debt
    # Wachstum: letztes Quartal vs. Vorjahresquartal
    qs = p["quartale"].get("umsatz", [])
    if len(qs) >= 5 and 350 <= (_d(qs[-1]["ende"]) - _d(qs[-5]["ende"])).days <= 380 and qs[-5]["wert"]:
        m["umsatzwachstum_yoy_quartal"] = qs[-1]["wert"] / qs[-5]["wert"] - 1
    fy = p["geschaeftsjahre"].get("umsatz", [])
    if len(fy) >= 2 and fy[-2]["wert"]:
        m["umsatzwachstum_letztes_gj"] = fy[-1]["wert"] / fy[-2]["wert"] - 1
    return m


def compare(old: dict | None, new: dict) -> list[dict]:
    """Veränderungen wichtiger Kennzahlen gegenüber dem vorherigen Profil (für Ereignisse)."""
    if not old:
        return []
    out = []
    for k in ("umsatz", "operatives_ergebnis", "nettoergebnis", "operativer_cashflow"):
        a, b = old.get("ttm", {}).get(k), new.get("ttm", {}).get(k)
        if a and b and a["bis"] != b["bis"] and a["wert"]:
            out.append({"kennzahl": f"{k}_ttm", "alt": a["wert"], "neu": b["wert"], "alt_bis": a["bis"],
                        "neu_bis": b["bis"], "veraenderung": b["wert"] / a["wert"] - 1})
    for k in ("bruttomarge", "operative_marge", "fcf_marge", "umsatzwachstum_yoy_quartal"):
        a, b = old.get("kennzahlen", {}).get(k), new.get("kennzahlen", {}).get(k)
        if a is not None and b is not None and abs(b - a) > 1e-9:
            out.append({"kennzahl": k, "alt": a, "neu": b, "veraenderung_pp": (b - a) * 100})
    return out
