"""Forward-Test FT1: vorab festgelegtes Regelwerk, virtuelles Kapital, append-only Journal.

Strategie (unverändert seit v1.0, siehe docs/REGELWERK_FT1.md):
- Portfolio 'BENCH': 100 % WORLD (MSCI-World-ETF), einmal kaufen und halten.
- Portfolio 'TREND': Tranchen WORLD 70 %, GOLD 20 %, BTC 10 %.
  Am Monatsende: Monatsschluss > Durchschnitt der letzten 12 Monatsschlüsse -> Tranche investiert,
  sonst Tranche in Cash (0 % Zins, konservativ).
- Ausführung: virtuell zum ersten Tagesschlusskurs NACH dem Datum der Signalerstellung.
- Kosten: ETF/ETC 0,2 % je Seite, Krypto 0,5 % je Seite.

Betriebsregeln v1.1/v1.2 (docs/REGELWERK_FT1_v1.1.md, _v1.2.md) – Datenqualität und Monatsabschluss:
- Signale nur für vollständig abgeschlossene und datumsgenau gegengeprüfte Monatsschlüsse.
- Ausführung nur zu abgeschlossenen, datumsgenau gegengeprüften Tagesschlusskursen.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from . import journal

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "journal" / "portfolio_state.json"
RULE = "FT1"
RULE_VERSION = "1.2"
SMA_MONTHS = 12
COSTS = {"equity_etf": 0.002, "gold_etc": 0.002, "crypto": 0.005}
PORTFOLIOS = {
    "BENCH": {"WORLD": 1.0},
    "TREND": {"WORLD": 0.70, "GOLD": 0.20, "BTC": 0.10},
}
START_CAPITAL = 10_000.0


# ---------------------------------------------------------------- Handelskalender
def _easter(y: int) -> date:
    """Ostersonntag (gregorianisch, anonymer Algorithmus)."""
    a, b, c = y % 19, y // 100, y % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l_ = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_) // 451
    month = (h + l_ - 7 * m + 114) // 31
    day = ((h + l_ - 7 * m + 114) % 31) + 1
    return date(y, month, day)


def xetra_holidays(y: int) -> set[date]:
    """Ganztägig geschlossene Xetra-Handelstage (Stand der Börse Frankfurt, regelmäßig zu prüfen)."""
    e = _easter(y)
    return {date(y, 1, 1), e - timedelta(days=2), e + timedelta(days=1), date(y, 5, 1),
            date(y, 12, 24), date(y, 12, 25), date(y, 12, 26), date(y, 12, 31)}


def expected_last_bar(month: pd.Period, asset_class: str) -> pd.Timestamp:
    """Datum des letzten regulären Tagesbalkens eines Monats."""
    d = month.end_time.date()
    if asset_class == "crypto":
        return pd.Timestamp(d)
    hol = xetra_holidays(d.year)
    while d.weekday() >= 5 or d in hol:
        d -= timedelta(days=1)
    return pd.Timestamp(d)


def last_completed_month(now_utc: pd.Timestamp) -> pd.Period:
    """Letzter vollständig abgelaufener Kalendermonat (Europe/Berlin)."""
    return now_utc.tz_convert("Europe/Berlin").tz_localize(None).to_period("M") - 1


# ---------------------------------------------------------------- Signale
def monthly_closes(daily: pd.Series, upto: pd.Period) -> pd.Series:
    m = daily.groupby(daily.index.to_period("M")).last()
    return m[m.index <= upto]


def trend_signal(daily: pd.Series, upto: pd.Period) -> dict | None:
    m = monthly_closes(daily, upto)
    if len(m) < SMA_MONTHS or m.index[-1] != upto:
        return None
    sma = m.tail(SMA_MONTHS).mean()
    last = m.iloc[-1]
    return {"monat": str(m.index[-1]), "monatsschluss": round(float(last), 4),
            "sma12": round(float(sma), 4), "investiert": bool(last > sma),
            "abstand_zur_sma": round(float(last / sma - 1), 4)}


def month_check(ps, now_utc: pd.Timestamp) -> dict:
    """Ist der letzte abgelaufene Monat vollständig, und ist sein Schlusskurs gegengeprüft?"""
    month = last_completed_month(now_utc)
    comp = ps.complete(now_utc)
    exp = expected_last_bar(month, ps.instrument.asset_class)
    in_month = comp[comp.index.to_period("M") == month]
    out = {"monat": str(month), "erwarteter_letzter_kurstag": str(exp.date())}
    if in_month.empty or in_month.index[-1] != exp:
        have = None if in_month.empty else str(in_month.index[-1].date())
        return {**out, "ok": False, "grund": f"Monatsschluss fehlt (letzter Kurs im Monat: {have})"}
    v = ps.verify(exp)
    if not v["ok"]:
        return {**out, "ok": False, "grund": f"Monatsschluss nicht bestätigt: {v['grund']}", "pruefung": v}
    return {**out, "ok": True, "pruefung": v}


# ---------------------------------------------------------------- Zustand
def load_state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {"rule": RULE,
            "portfolios": {p: {"cash": START_CAPITAL, "positions": {}, "history": []} for p in PORTFOLIOS},
            "pending": [], "signals_done": []}


def save_state(state: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False))


def _bar_date_of(ts_iso: str, asset_class: str) -> pd.Timestamp:
    t = pd.Timestamp(ts_iso)
    tz = "UTC" if asset_class == "crypto" else "Europe/Berlin"
    return t.tz_convert(tz).tz_localize(None).normalize()


# ---------------------------------------------------------------- Tageslauf
def step(series: dict, now_utc: pd.Timestamp | None = None) -> dict:
    """Ein Tageslauf: Orders ausführen, neue Monatssignale protokollieren, bewerten.
    series: key -> live_data.PriceSeries (fehlende Instrumente sind erlaubt)."""
    simulated = now_utc is not None
    now_utc = now_utc or pd.Timestamp.now(tz="UTC")
    stamp = now_utc.to_pydatetime() if simulated else None
    state = load_state()
    events, blocked, deferred = [], [], []

    # 1) Offene virtuelle Orders: erster abgeschlossener Schlusskurs nach Signaldatum, datumsgenau geprüft
    still = []
    for o in state["pending"]:
        ps = series.get(o["asset"])
        if ps is None:
            o["blockiert_grund"] = "keine Kursdaten abrufbar"
            blocked.append(o); still.append(o)
            continue
        comp = ps.complete(now_utc)
        avail = comp[comp.index > _bar_date_of(o["erstellt"], ps.instrument.asset_class)]
        if avail.empty:
            o.pop("blockiert_grund", None)
            still.append(o)          # regulär: noch kein Schlusskurs nach Signal
            continue
        d, px = avail.index[0], float(avail.iloc[0])
        check = ps.verify(d)
        if not check["ok"]:
            o["blockiert_grund"] = f"Ausführungskurs {d.date()} nicht bestätigt: {check['grund']}"
            o["blockiert_laeufe"] = o.get("blockiert_laeufe", 0) + 1
            blocked.append(o); still.append(o)
            continue
        pf = state["portfolios"][o["portfolio"]]
        cost_rate = COSTS[ps.instrument.asset_class]
        if o["aktion"] == "KAUF":
            total = _value(pf, series, now_utc)
            budget = min(total * o["zielgewicht"], pf["cash"])
            units = budget / (px * (1 + cost_rate))
            pf["cash"] -= units * px * (1 + cost_rate)
            pos = pf["positions"].setdefault(o["asset"], {"stueck": 0.0, "einstand": 0.0})
            pos["einstand"] = (pos["einstand"] * pos["stueck"] + units * px) / (pos["stueck"] + units)
            pos["stueck"] += units
            pos.update({"letzter_kurs": px, "kurs_datum": str(d.date())})
        else:
            pos = pf["positions"].pop(o["asset"], None)
            units = pos["stueck"] if pos else 0.0
            pf["cash"] += units * px * (1 - cost_rate)
        e = journal.append({"typ": "ausfuehrung", "regel": RULE, "regel_version": RULE_VERSION,
                            "signal_id": o["signal_id"], "portfolio": o["portfolio"], "asset": o["asset"],
                            "aktion": o["aktion"], "kursdatum": str(d.date()), "kurs": round(px, 4),
                            "stueck": round(units, 6), "kosten_satz": cost_rate, "quelle": ps.source,
                            "pruefung": check, "pruefstufe": check.get("stufe"),
                            "erkannt_tage_nach_kurs": int((now_utc.tz_convert("Europe/Berlin").tz_localize(None).normalize() - d).days)},
                           now=stamp)
        events.append(e)
    state["pending"] = still

    # 2) Neue Signale
    for pname, sleeves in PORTFOLIOS.items():
        for asset, w in sleeves.items():
            ps = series.get(asset)
            if pname == "BENCH":
                key = f"{pname}:{asset}:init"
                if key in state["signals_done"] or ps is None:
                    continue
                sig, check = {"investiert": True, "monat": "start", "regel_text": "Buy & Hold"}, None
            else:
                month = str(last_completed_month(now_utc))
                key = f"{pname}:{asset}:{month}"
                if key in state["signals_done"]:
                    continue
                if ps is None:
                    deferred.append({"portfolio": pname, "asset": asset, "monat": month, "grund": "keine Kursdaten"})
                    continue
                check = month_check(ps, now_utc)
                sig = trend_signal(ps.complete(now_utc), last_completed_month(now_utc)) if check["ok"] else None
                if sig is None:
                    deferred.append({"portfolio": pname, "asset": asset, "monat": month,
                                     "grund": check.get("grund") or "zu wenig Monatshistorie"})
                    continue
            held = _effective_held(state, pname, asset)
            action = "KAUF" if sig["investiert"] and not held else "VERKAUF" if not sig["investiert"] and held else "HALTEN"
            sid = f"{RULE}-{pname}-{asset}-{sig['monat']}"
            e = journal.append({"typ": "signal", "regel": RULE, "regel_version": RULE_VERSION, "signal_id": sid,
                                "portfolio": pname, "asset": asset, "aktion": action,
                                "zielgewicht": w if sig["investiert"] else 0.0,
                                "daten": {**sig, "quelle": ps.source, "letzter_kurs_datum": str(ps.last_date.date()),
                                          "monatsschluss_pruefung": check, "warnungen": ps.warnings},
                                "ausfuehrung": "erster abgeschlossener, gegengeprüfter Tagesschluss nach Signaldatum",
                                "kostenannahme": COSTS[ps.instrument.asset_class]}, now=stamp)
            events.append(e)
            state["signals_done"].append(key)
            if action in ("KAUF", "VERKAUF"):
                state["pending"].append({"signal_id": sid, "portfolio": pname, "asset": asset, "aktion": action,
                                         "zielgewicht": w, "erstellt": e["erstellt_utc"]})

    # 3) Bewertung (letzter abgeschlossener Kurs; bei Ausfall letzter bekannter Kurs, markiert)
    valuation, stale = {}, []
    for pname, pf in state["portfolios"].items():
        v = _value(pf, series, now_utc, stale)
        dates = [ps.complete(now_utc).index[-1] for ps in series.values() if len(ps.complete(now_utc))]
        if dates:
            d = str(max(dates).date())
            hist = pf["history"]
            if not hist or hist[-1]["datum"] != d:
                hist.append({"datum": d, "wert": round(v, 2)})
            else:
                hist[-1]["wert"] = round(v, 2)
        valuation[pname] = v
    save_state(state)
    return {"events": events, "valuation": valuation, "state": state,
            "blocked": blocked, "deferred": deferred, "stale_positions": sorted(set(stale))}


def _effective_held(state: dict, pname: str, asset: str) -> bool:
    held = asset in state["portfolios"][pname]["positions"]
    for o in state["pending"]:
        if o["portfolio"] == pname and o["asset"] == asset:
            held = o["aktion"] == "KAUF"
    return held


def _value(pf: dict, series: dict, now_utc, stale: list | None = None) -> float:
    v = pf["cash"]
    for a, pos in pf["positions"].items():
        ps = series.get(a)
        comp = ps.complete(now_utc) if ps is not None else pd.Series(dtype=float)
        if len(comp):
            pos["letzter_kurs"], pos["kurs_datum"] = float(comp.iloc[-1]), str(comp.index[-1].date())
        elif stale is not None:
            stale.append(a)
        v += pos["stueck"] * pos["letzter_kurs"]
    return v
