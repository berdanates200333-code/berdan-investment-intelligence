"""Kennzahlen, Wochenbericht und Abschlussbewertung (Paper-Trading). Reine Auswertung, keine Handelslogik."""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pandas as pd

# Vorab festgelegte Kriterien der Abschlussbewertung (v1.0). Änderungen nur prospektiv in neuer Version.
MIN_TRADES = 20            # unter 20 abgeschlossenen Trades ist die Stichprobe zu klein
MIN_TRADING_DAYS = 55      # ca. 11 Wochen Handelstage verarbeitet
MIN_DATA_QUALITY = 0.90    # Anteil Tage mit einwandfreien Daten
MAX_DD_LIMIT = 0.15        # tolerierter maximaler Verlust für ein "Bestanden"
MIN_EXCESS = 0.02          # Mindest-Mehrrendite gegenüber der Benchmark nach Kosten
EXTENSION_WEEKS = 4


def _maxdd(s: pd.Series) -> float:
    return float((s / s.cummax() - 1).min()) if len(s) else 0.0


def metrics(state: dict) -> dict:
    eq = pd.DataFrame(state["equity"])
    cap = state["kapital_eur"]
    cl = pd.DataFrame(state["closed"])
    m = {"tage": len(eq), "trades_abgeschlossen": len(cl), "trades_offen": len(state["positions"]),
         "ausfuehrungsfehler": len(state["failed"]), "kosten_eur": round(state["costs_eur"], 2)}
    if eq.empty:
        return {**m, "rendite_aktiv": 0.0, "rendite_bench": 0.0, "maxdd_aktiv": 0.0, "maxdd_bench": 0.0, "datenqualitaet": 0.0,
                "aktiv_eur": cap, "bench_eur": cap}
    m.update(aktiv_eur=float(eq["aktiv_eur"].iloc[-1]), bench_eur=float(eq["bench_eur"].iloc[-1]))
    m["rendite_aktiv"], m["rendite_bench"] = m["aktiv_eur"] / cap - 1, m["bench_eur"] / cap - 1
    m["maxdd_aktiv"], m["maxdd_bench"] = _maxdd(pd.concat([pd.Series([cap]), eq["aktiv_eur"]], ignore_index=True)), _maxdd(pd.concat([pd.Series([cap]), eq["bench_eur"]], ignore_index=True))
    m["datenqualitaet"] = float(eq["daten_ok"].mean())
    m["investiert_schnitt"] = float(1 - eq["cash_eur"].mean() / eq["aktiv_eur"].mean())
    if len(cl):
        w, l = cl[cl.pnl_eur > 0], cl[cl.pnl_eur <= 0]
        m.update(trefferquote=len(w) / len(cl), r_schnitt=float(cl.r_multiple.mean()), pnl_trades_eur=float(cl.pnl_eur.sum()),
                 profitfaktor=(float(w.pnl_eur.sum() / -l.pnl_eur.sum()) if len(l) and l.pnl_eur.sum() < 0 else None),
                 haltedauer_schnitt=float(cl.tage.mean()))
    return m


def _pct(x):
    return "n/a" if x is None else f"{x*100:+.2f} %"


def _table(rows, cols):
    if not rows:
        return "_keine_\n"
    out = "| " + " | ".join(cols) + " |\n|" + "---|" * len(cols) + "\n"
    for r in rows:
        out += "| " + " | ".join(str(r.get(c, "")) for c in cols) + " |\n"
    return out


def weekly_report(state: dict, journal_entries: list, week_end: date, version: str) -> str:
    ws = week_end - timedelta(days=6)
    inw = lambda s: ws <= date.fromisoformat(s) <= week_end  # noqa: E731
    m = metrics(state)
    plans = [e for e in journal_entries if e.get("typ") == "order_plan" and inw(e["datum"])]
    rejected = [e for e in journal_entries if e.get("typ") == "plan_verworfen" and inw(e["datum"])]
    closed = [c for c in state["closed"] if inw(c["ausstieg_datum"])]
    failed = [f for f in state["failed"] if inw(f["datum"])]
    s = f"# Paper-Trading Wochenbericht v{version} – Woche bis {week_end:%d.%m.%Y}\n\n"
    s += "_Rein virtuell. Keine Echtgeld-Orders, keine Anlageberatung. Alle Kurse sind verzögerte Tagesdaten._\n\n"
    s += f"## Portfolio vs. passive Benchmark (MSCI-World-ETF)\n- Aktiv: **{m['aktiv_eur']:.2f} €** ({_pct(m['rendite_aktiv'])}), max. Verlust vom Hoch {_pct(m['maxdd_aktiv'])}\n"
    s += f"- Benchmark: **{m['bench_eur']:.2f} €** ({_pct(m['rendite_bench'])}), max. Verlust {_pct(m['maxdd_bench'])}\n"
    s += f"- Differenz aktiv − Benchmark: {_pct(m['rendite_aktiv']-m['rendite_bench'])}-Punkte\n"
    s += f"- Kosten bisher: {m['kosten_eur']:.2f} € · abgeschlossene Trades: {m['trades_abgeschlossen']} · offen: {m['trades_offen']} · Ausführungsfehler: {m['ausfuehrungsfehler']}\n"
    s += f"- Neue Positionen pausiert: **{'JA seit ' + state['pause_seit'] if state['paused'] else 'nein'}** (Grenze −10 % vom Höchststand)\n"
    s += f"- Datenqualität (Tage ohne Datenproblem): {m['datenqualitaet']*100:.0f} % über {m['tage']} Handelstage\n\n"
    s += "## Offene Positionen\n" + _table([{"Ticker": t, "Stück": p["stueck"], "Einstieg": p["einstieg"], "Datum": p["einstieg_datum"], "Kurs": round(p["letzter_kurs"], 2),
                                              "Stop": p["stop"], "Ziel": p["ziel"], "Tage": p["tage"], "Grund": p["grund"][:60]} for t, p in state["positions"].items()],
                                            ["Ticker", "Stück", "Einstieg", "Datum", "Kurs", "Stop", "Ziel", "Tage", "Grund"])
    s += "\n## In dieser Woche abgeschlossene Trades\n" + _table(closed, ["ticker", "einstieg_datum", "ausstieg_datum", "einstieg_usd", "ausstieg_usd", "pnl_eur", "r_multiple", "kosten_eur", "grund"])
    s += "\n## Neue Orderpläne dieser Woche (dokumentiert vor Ausführung)\n" + _table(
        [{"Plan": e["id"], "Limit": e["limit"], "Stop": e["stop"], "Ziel": e["ziel"], "Stück": e["stueck"], "Risiko €": e["risikogrenze_eur"], "Grund": e["entscheidungsgrundlage"][:70]} for e in plans],
        ["Plan", "Limit", "Stop", "Ziel", "Stück", "Risiko €", "Grund"])
    s += "\n## Verworfene Kandidaten / fehlgeschlagene Ausführungen\n" + _table(
        [{"Datum": e["datum"], "Ticker": e["ticker"], "Grund": e["grund"][:110]} for e in rejected] + [{"Datum": f["datum"], "Ticker": f["ticker"], "Grund": f["grund"][:110]} for f in failed],
        ["Datum", "Ticker", "Grund"])
    s += f"\n## Hinweise\n- Strategieregeln: `docs/papertrading/STRATEGIE_v{version}.md` (eingefroren). Journal: `papertrading/v{version}/journal.jsonl` (Hash-Kette).\n"
    s += "- Kleine Stichprobe: Wochenergebnisse sind kein Beleg für Wirksamkeit.\n"
    return s


def final_evaluation(state: dict, today: date, end: date, version: str) -> str:
    m = metrics(state)
    reasons = []
    if m["trades_abgeschlossen"] < MIN_TRADES:
        reasons.append(f"nur {m['trades_abgeschlossen']} abgeschlossene Trades (Minimum {MIN_TRADES})")
    if m["tage"] < MIN_TRADING_DAYS:
        reasons.append(f"nur {m['tage']} verarbeitete Handelstage (Minimum {MIN_TRADING_DAYS})")
    if m["datenqualitaet"] < MIN_DATA_QUALITY:
        reasons.append(f"Datenqualität {m['datenqualitaet']*100:.0f} % (Minimum {MIN_DATA_QUALITY*100:.0f} %)")
    excess = m["rendite_aktiv"] - m["rendite_bench"]
    s = f"# Paper-Trading Abschlussbewertung v{version} – Stand {today:%d.%m.%Y}\n\n_Rein virtuell, keine Anlageberatung._\n\n"
    s += "## Kennzahlen\n"
    s += f"- Rendite aktiv: {_pct(m['rendite_aktiv'])} · Benchmark: {_pct(m['rendite_bench'])} · Differenz: {_pct(excess)}\n"
    s += f"- Maximaler Verlust vom Hoch: aktiv {_pct(m['maxdd_aktiv'])} · Benchmark {_pct(m['maxdd_bench'])}\n"
    s += f"- Kosten gesamt: {m['kosten_eur']:.2f} € · Trades: {m['trades_abgeschlossen']} abgeschlossen, {m['trades_offen']} offen · Ausführungsfehler: {m['ausfuehrungsfehler']}\n"
    if m.get("trefferquote") is not None:
        s += f"- Trefferquote {m['trefferquote']*100:.0f} % · Ø R-Multiple {m['r_schnitt']:.2f} · Profitfaktor {m['profitfaktor'] if m['profitfaktor'] is not None else 'n/a'} · Ø Haltedauer {m['haltedauer_schnitt']:.1f} Tage\n"
    s += f"- Datenqualität: {m['datenqualitaet']*100:.0f} % der Tage einwandfrei · Handelstage: {m['tage']}\n\n## Urteil (nach vorab festgelegten Regeln)\n"
    if reasons:
        s += f"**VERLÄNGERN um {EXTENSION_WEEKS} Wochen** – Stichprobe unzureichend: " + "; ".join(reasons) + ".\nKein Urteil über die Strategie möglich; Test läuft mit unveränderten Regeln weiter.\n"
        verdict = "VERLÄNGERN"
    elif excess >= MIN_EXCESS and m["maxdd_aktiv"] >= -MAX_DD_LIMIT:
        s += f"**Kriterien erfüllt (vorläufig):** Mehrrendite ≥ {MIN_EXCESS*100:.0f} Punkte nach Kosten und max. Verlust ≤ {MAX_DD_LIMIT*100:.0f} %. Aufgrund der kurzen Laufzeit weiter prospektiv beobachten, nicht als Beweis werten.\n"
        verdict = "KRITERIEN ERFÜLLT"
    else:
        s += "**Kriterien nicht erfüllt:** keine ausreichende Mehrrendite nach Kosten oder zu hoher Verlust. Regeländerungen nur als neue Version (prospektiv), alte Ergebnisse bleiben unverändert.\n"
        verdict = "NICHT ERFÜLLT"
    s += f"\nUrteil: {verdict}\n\n## Grenzen\n- Gebühren, Spread, Slippage, Ablehnungen sind Annahmen (siehe Strategiedokument), keine Brokerdaten.\n- Steuern nicht berücksichtigt; Tagesdaten inoffizieller Quellen; Universum von Hand festgelegt (mögliche Auswahlverzerrung).\n"
    return s
