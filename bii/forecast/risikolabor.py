"""Risikolabor: GLEICHE vorab dokumentierte Handelssignale (rules_v1_0, eingefroren) und GLEICHE Engine, nur das Risiko je Trade variiert (1/2/3 %).
Tagesweise Simulation ohne Look-ahead (Daten werden je Handelstag abgeschnitten), echte Kurslücken, Kosten, EZB-Wechselkurse.
Rein mechanische Signale (keine Claude-Analyse, kein Nachrichten-Veto) -> misst den Risikoeffekt, nicht Claudes Urteilsvermögen.
Bekannte Verzerrung: Das Universum sind die heutigen Mega-Caps (Survivorship Bias) – Renditen sind tendenziell zu optimistisch."""
from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

from ..papertrading import engine, rules_v1_0 as base
from . import calendars

# Profile: (Name, Risiko je Trade, max. Positionsgewicht, Drawdown-Pause, max. offenes Risiko). Raster ohne Pause und mit gleicher 30-%-Grenze isoliert den reinen Risikoeffekt
# (in der ersten Version begrenzte die 20-%-Positionsgrenze das Risiko bei 2 %/3 % unbemerkt auf ~1 % – dieser Fehler ist korrigiert).
PROFILE = (("Hauptkonto-Profil (1 %, 20 %, Pause −10 %)", 0.01, 0.20, 0.10, None), ("Offensiv-Profil (2 %, 30 %, Pause −15 %, ≤ 6 % offen)", 0.02, 0.30, 0.15, 0.06),
           ("Raster 1 % (Grenze 30 %, keine Pause)", 0.01, 0.30, 9.99, None), ("Raster 2 % (Grenze 30 %, keine Pause)", 0.02, 0.30, 9.99, None),
           ("Raster 3 % (Grenze 30 %, keine Pause)", 0.03, 0.30, 9.99, None))
LEVELS = tuple(p[1] for p in PROFILE)
PHASEN = (("2022-H2 Bärenmarkt", "2022-07-01", "2022-12-30"), ("2023 Erholung", "2023-03-01", "2023-08-31"), ("2024 Aufwärtstrend", "2024-06-03", "2024-11-29"),
          ("2025 Zollschock", "2025-02-03", "2025-07-31"), ("2026 jüngste Phase", "2026-03-02", "2026-10-30"))


class HistProvider:
    def __init__(self, frames: dict, fx: pd.Series):
        self.frames, self._fx, self.cut, self.log = frames, fx, None, []

    def ohlcv(self, s):
        df = self.frames.get(s)
        return None if df is None else df.loc[:self.cut]

    def fx(self):
        return self._fx.loc[:self.cut]

    def crosscheck(self, *a):
        return {"status": "bestaetigt"}

    def news(self, *a):
        return {"status": "nicht_genutzt", "treffer": [], "quellen": []}


def make_rules(start: str, end: str, risk: float, universe, bench_symbol="SPY", cap=0.20, pause=0.10, open_risk=None):
    ns = SimpleNamespace(**{k: v for k, v in vars(base).items() if not k.startswith("__")})
    ns.PARAMS = {**base.PARAMS, "risk_per_trade": risk, "max_new_per_day": 2, "max_position_weight": cap, "drawdown_pause": pause}
    if open_risk:
        ns.PARAMS["max_open_risk"] = open_risk
    ns.START, ns.END, ns.UNIVERSE, ns.VERSION = start, end, tuple(universe), f"LAB-{risk:.0%}-{cap}"
    ns.BENCH = {"symbol": bench_symbol, "name": "SPY (Lab-Referenz, USD)", "currency": "USD"}
    return ns


def run_window(frames: dict, fx: pd.Series, start: str, end: str, risk: float, universe, jdir: Path | None = None, cap=0.20, pause=0.10, open_risk=None, name=None) -> dict:
    rules = make_rules(start, end, risk, universe, cap=cap, pause=pause, open_risk=open_risk)
    st = engine.new_state(rules)
    prov = HistProvider(frames, fx)
    jp = (jdir or Path(tempfile.mkdtemp())) / f"lab_{risk}_{cap}_{pause}.jsonl"
    days = [d for d in frames["SPY"].index if pd.Timestamp(start) <= d <= pd.Timestamp(end)]
    for d in days:
        prov.cut = d
        now = (calendars.session_close("XNYS", d) + pd.Timedelta(minutes=50)).to_pydatetime()
        engine.run(st, prov, rules, jp, now=now, ende=end)
    eq = np.array([10_000.0] + [e["aktiv_eur"] for e in st["equity"]])
    peak = np.maximum.accumulate(eq)
    rets = eq[1:] / eq[:-1] - 1
    closed = st["closed"]
    plans = {}
    import json
    for line in jp.read_text().splitlines() if jp.exists() else []:
        e = json.loads(line)
        if e["typ"] == "order_plan":
            plans[e["id"]] = e
    ratios = [c["pnl_eur"] / plans[c["plan_id"]]["risikogrenze_eur"] for c in closed if c["plan_id"] in plans and plans[c["plan_id"]]["risikogrenze_eur"]]
    spy = frames["SPY"].loc[:pd.Timestamp(end)]
    spy0, spy1 = spy.loc[pd.Timestamp(start):].close.iloc[0], spy.close.iloc[-1]
    return {"profil": name or f"{risk:.0%}", "risiko": risk, "rendite_pct": (eq[-1] / 10_000 - 1) * 100, "maxdd_pct": float((eq / peak - 1).min() * 100), "vol_ann_pct": float(rets.std(ddof=1) * np.sqrt(252) * 100) if len(rets) > 5 else None,
            "trades": len(closed), "trefferquote_pct": (sum(c["pnl_eur"] > 0 for c in closed) / len(closed) * 100) if closed else None, "kosten_eur": st["costs_eur"],
            "pausiert": st["paused"], "schlechtester_trade_in_risiko": min(ratios) if ratios else None, "gap_stops": sum("Kurslücke" in c["grund"] for c in closed),
            "spy_buy_hold_pct": (spy1 / spy0 - 1) * 100, "handelstage": len(days)}


def markdown(results: dict) -> str:
    t = ("# Risikolabor – 1 % / 2 % / 3 % Risiko je Trade bei identischen Signalen\n\n"
         "Mechanische v1.0-Swing-Signale (eingefroren), gemeinsame Engine, echte Kurslücken, Kosten und EZB-Wechselkurse; je Phase 10.000 € Start. **Kein Claude-Urteil, kein Nachrichten-Veto.** "
         "Universum = heutige Mega-Caps (Survivorship Bias, Renditen eher zu optimistisch). Wenige Trades je Phase: Unterschiede sind nicht statistisch belastbar.\n\n")
    t += "| Phase | Profil | Rendite % | Max. Rückgang % | Vol. p.a. % | Trades | Treffer % | Kosten € | Schlechtester Trade (× Risiko) | Lücken-Stops | SPY B&H % |\n|---|---|---|---|---|---|---|---|---|---|---|\n"
    for ph, rows in results.items():
        for r in rows:
            f = lambda k, fmt: "–" if r[k] is None else format(r[k], fmt)  # noqa: E731
            t += (f"| {ph} | {r['profil']} | {r['rendite_pct']:+.2f} | {r['maxdd_pct']:.2f} | {f('vol_ann_pct', '.1f')} | {r['trades']} | {f('trefferquote_pct', '.0f')} | {r['kosten_eur']:.0f} | "
                  f"{f('schlechtester_trade_in_risiko', '+.2f')} | {r['gap_stops']} | {r['spy_buy_hold_pct']:+.1f} |\n")
    agg = {}
    for rows in results.values():
        for r in rows:
            a = agg.setdefault(r["profil"], {"ret": [], "dd": []})
            a["ret"].append(r["rendite_pct"]); a["dd"].append(r["maxdd_pct"])
    t += "\n## Über alle Phasen\n\n| Profil | Ø Rendite % | Schlechteste Phase % | Ø max. Rückgang % | schlechtester Rückgang % | Rendite je 1 % Rückgang |\n|---|---|---|---|---|---|\n"
    for k, a in agg.items():
        t += f"| {k} | {np.mean(a['ret']):+.2f} | {min(a['ret']):+.2f} | {np.mean(a['dd']):.2f} | {min(a['dd']):.2f} | {np.mean(a['ret']) / abs(np.mean(a['dd'])) if np.mean(a['dd']) else float('nan'):+.2f} |\n"
    return t
