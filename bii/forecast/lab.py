"""Performance Lab: Kennzahlen beider virtueller Konten, Vergleich mit EUNL und passivem Mix, Auswahl- vs. Größeneffekt. Reine Auswertung."""
from __future__ import annotations

import json
import math
from pathlib import Path

from .. import journal

ROOT = Path(__file__).resolve().parents[2]
ZIELE = ((10, "außergewöhnlich"), (5, "stark"), (3, "interessant"))


def _jl(p: Path):
    return journal.read(p) if p.exists() else []


def load_account(ki: str, root: Path = ROOT):
    sp = root / "forecast" / ki / "konto" / "state.json"
    if not sp.exists():
        return None
    return json.loads(sp.read_text()), _jl(root / "forecast" / ki / "konto" / "handel.jsonl")


def metrics(state: dict, entries: list) -> dict:
    cap = state["kapital_eur"]
    eq = [cap] + [e["aktiv_eur"] for e in state["equity"]]
    bench = [cap] + [e["bench_eur"] for e in state["equity"]]
    peak, mdd = eq[0], 0.0
    for v in eq:
        peak = max(peak, v)
        mdd = min(mdd, v / peak - 1)
    rets = [eq[i] / eq[i - 1] - 1 for i in range(1, len(eq))]
    vol = (math.sqrt(sum((r - sum(rets) / len(rets)) ** 2 for r in rets) / (len(rets) - 1)) * math.sqrt(252)) if len(rets) >= 5 else None
    plans = {e["id"]: e for e in entries if e["typ"] == "order_plan"}
    closed = state["closed"]
    risk_sum = sum(plans[c["plan_id"]]["risikogrenze_eur"] for c in closed if c["plan_id"] in plans)
    pnl_closed = sum(c["pnl_eur"] for c in closed)
    open_risk = sum(max(p["einstieg"] - p["stop"], 0) * p["stueck"] / p.get("fx_einstieg", 1.1) for p in state["positions"].values())
    open_val = sum(p["stueck"] * p["letzter_kurs"] / p.get("fx_einstieg", 1.1) for p in state["positions"].values())
    worst_ratio = min((c["pnl_eur"] / plans[c["plan_id"]]["risikogrenze_eur"] for c in closed if c["plan_id"] in plans and plans[c["plan_id"]]["risikogrenze_eur"]), default=None)
    return {"kapital": cap, "stand": eq[-1], "pnl_eur": eq[-1] - cap, "pnl_pct": (eq[-1] / cap - 1) * 100, "maxdd_pct": mdd * 100, "vol_ann_pct": vol * 100 if vol is not None else None,
            "bench_eur": bench[-1], "bench_pct": (bench[-1] / cap - 1) * 100, "tage": len(state["equity"]), "trades": len(closed), "offen": len(state["positions"]),
            "treffer": (sum(c["pnl_eur"] > 0 for c in closed) / len(closed) * 100) if closed else None, "kosten_eur": state["costs_eur"], "pausiert": state["paused"],
            "gewinn_je_risiko": (pnl_closed / risk_sum) if risk_sum else None, "offenes_risiko_eur": open_risk, "stress_verlust_eur": open_risk + 0.03 * open_val,
            "schlechtester_trade_in_risiko": worst_ratio}


def mix_pct(root: Path = ROOT):
    """Passiver Mix 60 % EUNL / 30 % Gold (GLD in EUR) / 10 % Bargeld seit dem ersten Log-Eintrag (letzter Schluss vor dem Start)."""
    rows = [json.loads(x) for x in (root / "forecast" / "daten" / "mix.jsonl").read_text().splitlines() if x.strip()] if (root / "forecast" / "daten" / "mix.jsonl").exists() else []
    if len(rows) < 2:
        return None
    a, b = rows[0], rows[-1]
    gold = (b["gld_usd"] / b["usd_je_eur"]) / (a["gld_usd"] / a["usd_je_eur"])
    return (0.6 * b["eunl_eur"] / a["eunl_eur"] + 0.3 * gold + 0.1 - 1) * 100


def ziel_label(pct: float) -> str:
    for z, name in ZIELE:
        if pct >= z:
            return f"{name} (≥ +{z} %)"
    return "unter der ersten Zielmarke (+3 %)"


def attribution(main, off, root: Path = ROOT, source: str = "claude"):
    """Trennt Größeneffekt (gleiche Prognose, anderes Risiko) und Auswahleffekt (nur im Offensivkonto gehandelte Prognosen)."""
    if not main or not off:
        return None
    prog = {p["prognose_id"]: p for p in _jl(root / "forecast" / source / "prognosen.jsonl")}
    pm = {e["id"]: e for e in main[1] if e["typ"] == "order_plan"}
    po = {e["id"]: e for e in off[1] if e["typ"] == "order_plan"}
    main_by = {pm[c["plan_id"]]["prognose_id"]: c for c in main[0]["closed"] if c["plan_id"] in pm}
    same, only = [], []
    for c in off[0]["closed"]:
        pid = po[c["plan_id"]]["prognose_id"] if c["plan_id"] in po else None
        (only if prog.get(pid, {}).get("nur_offensiv") else same).append((pid, c))
    size_pnl_off = sum(c["pnl_eur"] for pid, c in same if pid in main_by)
    size_pnl_main = sum(main_by[pid]["pnl_eur"] for pid, c in same if pid in main_by)
    return {"gleiche_signale_n": sum(1 for pid, _ in same if pid in main_by), "gleiche_signale_pnl_offensiv": size_pnl_off, "gleiche_signale_pnl_haupt": size_pnl_main,
            "nur_offensiv_n": len(only), "nur_offensiv_pnl": sum(c["pnl_eur"] for _, c in only)}


def verdict(main_m, off_m, attr) -> str:
    """Ehrliche Einordnung: bessere Chancenwahl oder nur mehr Marktrisiko?"""
    if not main_m or not off_m or off_m["trades"] < 5 or main_m["trades"] < 5:
        return "Zu wenig abgeschlossene Trades (< 5 je Konto) für eine Aussage über Chancenwahl vs. Risikoaufschlag."
    ratio = (off_m["pnl_eur"] / main_m["pnl_eur"]) if main_m["pnl_eur"] else None
    msg = f"Offensiv {off_m['pnl_eur']:+.0f} € vs. Haupt {main_m['pnl_eur']:+.0f} €; Gewinn je Risiko {off_m['gewinn_je_risiko'] or 0:.2f} vs. {main_m['gewinn_je_risiko'] or 0:.2f}."
    if attr and attr["gleiche_signale_n"] >= 3:
        msg += f" Gleiche Signale ({attr['gleiche_signale_n']}): offensiv {attr['gleiche_signale_pnl_offensiv']:+.0f} € vs. haupt {attr['gleiche_signale_pnl_haupt']:+.0f} € (reiner Größeneffekt)."
    if attr and attr["nur_offensiv_n"] >= 3:
        msg += f" Nur-Offensiv-Signale ({attr['nur_offensiv_n']}): {attr['nur_offensiv_pnl']:+.0f} € (Auswahleffekt)."
    if off_m["gewinn_je_risiko"] is not None and main_m["gewinn_je_risiko"] is not None:
        msg += " Mehr Gewinn je Risiko spricht für bessere Chancenwahl, gleicher/ niedrigerer Wert für reine Risikoausweitung." if off_m["gewinn_je_risiko"] > main_m["gewinn_je_risiko"] else " Der Gewinn je Risiko ist nicht höher – der Mehrertrag (falls vorhanden) stammt aus größerem Marktrisiko."
    return msg


def risk_analysis_text(ki: str, state: dict, entries: list) -> str:
    """Vollständige Risikoanalyse (bei Pause bzw. auf Abruf): Verluste im Verhältnis zum geplanten Risiko, Kurslücken, Verlustserien, Drawdown, Stress."""
    m = metrics(state, entries)
    plans = {e["id"]: e for e in entries if e["typ"] == "order_plan"}
    t = f"# Risikoanalyse {ki}\n\nStand {state['last_date']} · Konto {m['stand']:.2f} € ({m['pnl_pct']:+.2f} %) · max. Rückgang {m['maxdd_pct']:.2f} % · Pause: {state['paused']} seit {state.get('pause_seit')}\n\n"
    t += "| Trade | Ergebnis € | geplantes Risiko € | Vielfaches | Ausstiegsgrund | Tage |\n|---|---|---|---|---|---|\n"
    streak = best = 0
    for c in state["closed"]:
        pl = plans.get(c["plan_id"], {}).get("risikogrenze_eur")
        t += f"| {c['ticker']} | {c['pnl_eur']:+.2f} | {pl if pl is not None else '–'} | {'–' if not pl else format(c['pnl_eur'] / pl, '+.2f')} | {c['grund']} | {c['tage']} |\n"
        streak = streak + 1 if c["pnl_eur"] < 0 else 0
        best = max(best, streak)
    gaps = [c for c in state["closed"] if "Kurslücke" in c["grund"] or "Gap" in c["grund"]]
    t += f"\n- Längste Verlustserie: {best} · Ausstiege durch Kurslücken: {len(gaps)} (Stops sind keine garantierte Verlustgrenze)\n"
    t += f"- Offene Positionen: {m['offen']} · offenes geplantes Risiko {m['offenes_risiko_eur']:.0f} € · Stressverlust (+3 % Lücke auf alle Stops) {m['stress_verlust_eur']:.0f} €\n"
    t += "- Maßnahmen laut Regelwerk: keine neuen Positionen bis zur dokumentierten manuellen Freigabe; Bestandspositionen laufen über Stop/Ziel/Zeitstopp weiter.\n"
    return t
