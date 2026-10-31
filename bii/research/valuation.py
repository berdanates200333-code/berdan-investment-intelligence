"""Bewertung: Multiplikatoren, Reverse-DCF („was ist eingepreist?“) und Szenariowerte.

Alles deterministische Rechnung mit offengelegten Annahmen – keine Prognose, keine KI.
Kursdaten: Yahoo Finance (inoffiziell, nur private Auswertung) mit Stooq als Gegenprüfung.
"""
from __future__ import annotations

import io

import pandas as pd

from .http import Client

DISCOUNT = 0.09        # Diskontsatz (Annahme: grob Eigenkapitalkosten großer US-Tech-Werte)
TERMINAL_G = 0.03      # langfristiges Wachstum nach Jahr 10
YEARS = 10


def price(client: Client, ticker: str) -> dict:
    """Letzter Tagesschluss mit Zweitquelle. Rückgabe enthält Quelle, Datum und Prüfstatus."""
    out: dict = {"ticker": ticker}
    try:
        j, meta = client.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range=1mo&interval=1d",
                             "Yahoo Finance (inoffiziell)")
        res = j["chart"]["result"][0]
        ts = pd.to_datetime(res["timestamp"], unit="s", utc=True).tz_convert("America/New_York")
        closes = pd.Series(res["indicators"]["quote"][0]["close"], index=ts.normalize().tz_localize(None)).dropna()
        out.update(kurs=float(closes.iloc[-1]), datum=str(closes.index[-1].date()), quelle="Yahoo Finance (inoffiziell)",
                   waehrung=res.get("meta", {}).get("currency"), url=meta["url"], abgerufen_utc=meta["abgerufen_utc"])
    except Exception as e:  # noqa: BLE001
        out["fehler_primaer"] = str(e)[:160]
    try:
        txt, meta = client.get(f"https://stooq.com/q/d/l/?s={ticker.lower()}.us&i=d", "Stooq", kind="text")
        df = pd.read_csv(io.StringIO(txt))
        if "Close" not in df.columns:
            raise ValueError("Stooq: unerwartetes Format")
        s = df.set_index(pd.to_datetime(df["Date"]))["Close"].astype(float)
        if "kurs" not in out:
            out.update(kurs=float(s.iloc[-1]), datum=str(s.index[-1].date()), quelle="Stooq", waehrung="USD",
                       url=meta["url"], abgerufen_utc=meta["abgerufen_utc"])
        else:
            d = pd.Timestamp(out["datum"])
            if d in s.index:
                dev = abs(out["kurs"] / float(s.loc[d]) - 1)
                out["pruefung"] = {"quelle": "Stooq", "datum": out["datum"], "abweichung": round(dev, 5),
                                   "stufe": "bestaetigt" if dev <= 0.01 else "abweichung"}
            else:
                out["pruefung"] = {"quelle": "Stooq", "stufe": "kein_kurs_am_datum"}
    except Exception as e:  # noqa: BLE001
        out["fehler_zweitquelle"] = str(e)[:160]
        out.setdefault("pruefung", {"stufe": "zweitquelle_ausgefallen"})
    return out


def multiples(k: dict, px: dict, shares: float | None) -> dict:
    if not px.get("kurs") or not shares:
        return {}
    mcap = px["kurs"] * shares
    ev = mcap - (k.get("nettoliquiditaet") or 0.0)
    m = {"marktkapitalisierung": mcap, "unternehmenswert": ev}
    if k.get("nettoergebnis_ttm"):
        m["kgv_ttm"] = mcap / k["nettoergebnis_ttm"]
    if k.get("umsatz_ttm"):
        m["ev_umsatz_ttm"] = ev / k["umsatz_ttm"]
    if k.get("fcf_ttm"):
        m["fcf_rendite_ttm"] = k["fcf_ttm"] / mcap
        sbc = k.get("aktienverguetung_ttm") or 0.0
        m["fcf_rendite_nach_sbc_ttm"] = (k["fcf_ttm"] - sbc) / mcap
    if k.get("operatives_ergebnis_ttm"):
        m["ev_ebit_ttm"] = ev / k["operatives_ergebnis_ttm"]
    return m


def dcf_value(revenue0: float, growth: float, fcf_margin: float, years: int = YEARS,
              r: float = DISCOUNT, g: float = TERMINAL_G) -> float:
    """Barwert der freien Cashflows bei konstantem Umsatzwachstum und konstanter FCF-Marge."""
    pv, rev = 0.0, revenue0
    for t in range(1, years + 1):
        rev *= 1 + growth
        pv += rev * fcf_margin / (1 + r) ** t
    tv = rev * (1 + g) * fcf_margin / (r - g)
    return pv + tv / (1 + r) ** years


def implied_growth(ev: float, revenue0: float, fcf_margin: float) -> float | None:
    """Reverse-DCF: Welches jährliche Umsatzwachstum (10 Jahre) rechtfertigt den heutigen Unternehmenswert
    bei der angegebenen FCF-Marge? Bisektion zwischen −30 % und +80 %."""
    if not (ev and revenue0 and fcf_margin and fcf_margin > 0):
        return None
    lo, hi = -0.30, 0.80
    if dcf_value(revenue0, hi, fcf_margin) < ev:
        return None
    for _ in range(80):
        mid = (lo + hi) / 2
        if dcf_value(revenue0, mid, fcf_margin) < ev:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def scenario_value(sc: dict, k: dict, shares: float, net_cash: float) -> dict:
    """Szenario: Umsatz-CAGR über n Jahre, FCF-Marge im Zieljahr, Bewertungsmultiple (EV/FCF) am Ende,
    jährliche Verwässerung. Ergebnis: Wert je Aktie im Zieljahr und heute (diskontiert)."""
    n = sc.get("jahre", 5)
    rev_n = k["umsatz_ttm"] * (1 + sc["umsatz_cagr"]) ** n
    fcf_n = rev_n * sc["fcf_marge"]
    ev_n = fcf_n * sc["ev_fcf_multiple"]
    shares_n = shares * (1 + sc.get("verwaesserung_pa", 0.0)) ** n
    per_share_n = (ev_n + net_cash) / shares_n
    today = per_share_n / (1 + DISCOUNT) ** n
    return {"umsatz_zieljahr": rev_n, "fcf_zieljahr": fcf_n, "wert_je_aktie_zieljahr": per_share_n,
            "wert_je_aktie_heute": today}
