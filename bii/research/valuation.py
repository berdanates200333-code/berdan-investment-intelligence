"""Bewertung mit Szenarien (Discounted Cashflow) und Rückwärts-DCF ("was ist eingepreist?").

Exakte Rechnung in Python. Die ANNAHMEN (Wachstum, Margen, Diskontsatz) stehen offen in
research/theses/<TICKER>.json und werden von einer KI-Analyse oder manuell gesetzt und begründet.
Alle Beträge in der Berichtswährung des Unternehmens (hier USD).
"""
from __future__ import annotations


def dcf(revenue0: float, growth_1_5: float, growth_6_10: float, fcf_margin: float, discount: float,
        terminal_growth: float, net_cash: float, shares: float, share_change_pa: float = 0.0,
        margin_start: float | None = None) -> dict:
    """10-Jahres-DCF. Die FCF-Marge läuft linear von margin_start (Standard: Zielmarge) auf fcf_margin."""
    if discount <= terminal_growth:
        raise ValueError("Diskontsatz muss über der Wachstumsrate der Endphase liegen")
    m0 = fcf_margin if margin_start is None else margin_start
    rev, pv, rows = revenue0, 0.0, []
    for y in range(1, 11):
        rev *= 1 + (growth_1_5 if y <= 5 else growth_6_10)
        margin = m0 + (fcf_margin - m0) * min(y / 5, 1.0)
        fcf = rev * margin
        pv_y = fcf / (1 + discount) ** y
        pv += pv_y
        rows.append({"jahr": y, "umsatz": rev, "fcf_marge": margin, "fcf": fcf, "barwert": pv_y})
    tv = rows[-1]["fcf"] * (1 + terminal_growth) / (discount - terminal_growth)
    pv_tv = tv / (1 + discount) ** 10
    equity = pv + pv_tv + net_cash
    shares_future = shares * (1 + share_change_pa) ** 5   # Verwässerung/Rückkauf, vereinfacht über 5 Jahre
    return {"unternehmenswert_barwert_fcf": pv, "barwert_endwert": pv_tv, "anteil_endwert": pv_tv / (pv + pv_tv),
            "eigenkapitalwert": equity, "wert_je_aktie": equity / shares_future, "jahre": rows}


def implied_growth(market_cap: float, revenue0: float, fcf_margin: float, discount: float,
                   terminal_growth: float, net_cash: float, lo: float = -0.3, hi: float = 1.0) -> float | None:
    """Konstante Umsatzwachstumsrate (10 Jahre) bei konstanter heutiger FCF-Marge, die den Börsenwert erklärt."""
    if fcf_margin <= 0:
        return None

    def val(g):
        return dcf(revenue0, g, g, fcf_margin, discount, terminal_growth, net_cash, 1.0)["eigenkapitalwert"]

    if val(lo) > market_cap or val(hi) < market_cap:
        return None
    for _ in range(100):
        mid = (lo + hi) / 2
        if val(mid) < market_cap:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def scenarios(base: dict, assumptions: dict, price: float | None) -> dict:
    """base: revenue0, fcf_margin_ttm, net_cash, shares. assumptions: aus der These (bear/base/bull)."""
    out = {"annahmen": assumptions, "ausgangswerte": base, "szenarien": {}}
    d, tg = assumptions["diskontsatz"], assumptions["endwachstum"]
    for name in ("negativ", "neutral", "positiv"):
        a = assumptions["szenarien"][name]
        r = dcf(base["revenue0"], a["wachstum_j1_5"], a["wachstum_j6_10"], a["fcf_marge_ziel"], d, tg,
                base["net_cash"], base["shares"], a.get("aktienzahl_aenderung_pa", 0.0), base.get("fcf_margin_ttm"))
        res = {"wert_je_aktie": r["wert_je_aktie"], "anteil_endwert": r["anteil_endwert"],
               "umsatz_jahr10": r["jahre"][-1]["umsatz"], "begruendung": a.get("begruendung", "")}
        if price:
            res["abstand_zum_kurs"] = r["wert_je_aktie"] / price - 1
        out["szenarien"][name] = res
    if price and base.get("fcf_margin_ttm"):
        mc = price * base["shares"]
        out["marktkapitalisierung"] = mc
        out["eingepreistes_wachstum_10j"] = implied_growth(mc, base["revenue0"], base["fcf_margin_ttm"], d, tg, base["net_cash"])
        w = assumptions.get("wahrscheinlichkeiten")
        if w:
            out["gewichteter_wert_je_aktie"] = sum(out["szenarien"][k]["wert_je_aktie"] * w[k] for k in w)
    return out


def entry_check(val: dict, price: float | None, rules: dict) -> dict:
    """Einstiegskriterium der These prüfen (Beobachtung, kein Handel)."""
    if not price or not rules:
        return {"erfuellt": False, "grund": "kein Kurs oder keine Einstiegsregel"}
    ref = val["szenarien"][rules.get("referenz", "neutral")]["wert_je_aktie"]
    limit = ref * (1 - rules.get("sicherheitsmarge", 0.2))
    return {"erfuellt": price <= limit, "kurs": price, "schwelle": limit,
            "regel": f"Kurs ≤ {rules.get('referenz', 'neutral')}-Wert × (1 − {rules.get('sicherheitsmarge', 0.2):.0%})"}
