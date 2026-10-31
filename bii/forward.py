"""Forward-Test FT1: vorab festgelegtes Regelwerk, virtuelles Kapital, append-only Journal.

Regelwerk (siehe docs/REGELWERK_FT1.md, Änderungen nur mit neuer Version FT2):
- Portfolio 'BENCH': 100 % WORLD (MSCI-World-ETF), einmal kaufen und halten.
- Portfolio 'TREND': Tranchen WORLD 70 %, GOLD 20 %, BTC 10 %.
  Am Monatsende: Monatsschluss > Durchschnitt der letzten 12 Monatsschlüsse -> Tranche investiert,
  sonst Tranche in Cash (0 % Zins, konservativ).
- Ausführung: virtuell zum ersten Tagesschlusskurs NACH dem Zeitpunkt der Signalerstellung.
- Kosten: ETF/ETC 0,2 % je Seite, Krypto 0,5 % je Seite (Gebühr + Spread + Slippage).
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from . import journal

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "journal" / "portfolio_state.json"
RULE = "FT1"
SMA_MONTHS = 12
COSTS = {"equity_etf": 0.002, "gold_etc": 0.002, "crypto": 0.005}
PORTFOLIOS = {
    "BENCH": {"WORLD": 1.0},
    "TREND": {"WORLD": 0.70, "GOLD": 0.20, "BTC": 0.10},
}
START_CAPITAL = 10_000.0


def monthly_closes(daily: pd.Series, today: pd.Timestamp) -> pd.Series:
    """Letzter Schlusskurs je abgeschlossenem Kalendermonat (laufender Monat ausgeschlossen)."""
    m = daily.groupby(daily.index.to_period("M")).last()
    return m[m.index < today.to_period("M")]


def trend_signal(daily: pd.Series, today: pd.Timestamp) -> dict | None:
    m = monthly_closes(daily, today)
    if len(m) < SMA_MONTHS:
        return None
    sma = m.tail(SMA_MONTHS).mean()
    last = m.iloc[-1]
    return {"monat": str(m.index[-1]), "monatsschluss": round(float(last), 4),
            "sma12": round(float(sma), 4), "investiert": bool(last > sma),
            "abstand_zur_sma": round(float(last / sma - 1), 4)}


def load_state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {"rule": RULE,
            "portfolios": {p: {"cash": START_CAPITAL, "positions": {}, "history": []} for p in PORTFOLIOS},
            "pending": [], "signals_done": []}


def save_state(state: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False))


def step(series: dict, today: pd.Timestamp) -> dict:
    """Ein Tageslauf: Orders ausführen, neue Monatssignale protokollieren, bewerten.
    series: key -> live_data.PriceSeries"""
    state = load_state()
    events = []

    # 1) Offene virtuelle Orders ausführen (erster Schluss NACH Signalerstellung)
    still = []
    for o in state["pending"]:
        ps = series.get(o["asset"])
        created = pd.Timestamp(o["erstellt"][:10])
        avail = ps.close[ps.close.index > created] if ps is not None else pd.Series(dtype=float)
        if ps is None or avail.empty or ps.warnings and any("Datenprüfung" in w for w in ps.warnings):
            still.append(o)
            continue
        d, px = avail.index[0], float(avail.iloc[0])
        pf = state["portfolios"][o["portfolio"]]
        cost_rate = COSTS[ps.instrument.asset_class]
        if o["aktion"] == "KAUF":
            total = _value(pf, series)
            budget = min(total * o["zielgewicht"], pf["cash"])
            units = budget / (px * (1 + cost_rate))
            pf["cash"] -= units * px * (1 + cost_rate)
            pos = pf["positions"].setdefault(o["asset"], {"stueck": 0.0, "einstand": 0.0})
            pos["einstand"] = (pos["einstand"] * pos["stueck"] + units * px) / (pos["stueck"] + units)
            pos["stueck"] += units
        else:
            pos = pf["positions"].pop(o["asset"], None)
            units = pos["stueck"] if pos else 0.0
            pf["cash"] += units * px * (1 - cost_rate)
        e = journal.append({"typ": "ausfuehrung", "regel": RULE, "signal_id": o["signal_id"],
                            "portfolio": o["portfolio"], "asset": o["asset"], "aktion": o["aktion"],
                            "kursdatum": str(d.date()), "kurs": round(px, 4), "stueck": round(units, 6),
                            "kosten_satz": cost_rate, "quelle": ps.source})
        events.append(e)
    state["pending"] = still

    # 2) Neue Monatssignale
    for pname, sleeves in PORTFOLIOS.items():
        for asset, w in sleeves.items():
            ps = series.get(asset)
            if ps is None:
                continue
            if pname == "BENCH":
                key = f"{pname}:{asset}:init"
                if key in state["signals_done"]:
                    continue
                sig = {"investiert": True, "monat": "start", "regel_text": "Buy & Hold"}
            else:
                sig = trend_signal(ps.close, today)
                if sig is None:
                    continue
                key = f"{pname}:{asset}:{sig['monat']}"
                if key in state["signals_done"]:
                    continue
            held = asset in state["portfolios"][pname]["positions"] or any(
                o["portfolio"] == pname and o["asset"] == asset and o["aktion"] == "KAUF" for o in state["pending"])
            action = "KAUF" if sig["investiert"] and not held else "VERKAUF" if not sig["investiert"] and held else "HALTEN"
            sid = f"{RULE}-{pname}-{asset}-{sig['monat']}"
            e = journal.append({"typ": "signal", "regel": RULE, "signal_id": sid, "portfolio": pname, "asset": asset,
                                "aktion": action, "zielgewicht": w if sig["investiert"] else 0.0,
                                "daten": {**sig, "quelle": ps.source, "letzter_kurs_datum": str(ps.last_date.date()),
                                          "gegenpruefung": ps.cross_check, "warnungen": ps.warnings},
                                "ausfuehrung": "erster Tagesschluss nach Signalerstellung",
                                "kostenannahme": COSTS[ps.instrument.asset_class]})
            events.append(e)
            state["signals_done"].append(key)
            if action in ("KAUF", "VERKAUF"):
                state["pending"].append({"signal_id": sid, "portfolio": pname, "asset": asset, "aktion": action,
                                         "zielgewicht": w, "erstellt": e["erstellt_utc"]})

    # 3) Bewertung
    valuation = {}
    for pname, pf in state["portfolios"].items():
        v = _value(pf, series)
        hist = pf["history"]
        date = str(max(ps.last_date for ps in series.values()).date())
        if not hist or hist[-1]["datum"] != date:
            hist.append({"datum": date, "wert": round(v, 2)})
        else:
            hist[-1]["wert"] = round(v, 2)
        valuation[pname] = v
    save_state(state)
    return {"events": events, "valuation": valuation, "state": state}


def _value(pf: dict, series: dict) -> float:
    v = pf["cash"]
    for a, pos in pf["positions"].items():
        v += pos["stueck"] * series[a].last
    return v
