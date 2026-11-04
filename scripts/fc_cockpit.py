"""Tages-Cockpit für den Chat: Portfolio, Einschätzungen, Kursprognosen, fällige Bewertungen, Gewinn/Verlust, technischer Status.
Aufruf: python scripts/fc_cockpit.py [claude|vergleich]   ('vergleich' zeigt auch ChatGPT – erst NACH der eigenen Tagesprognose verwenden)"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bii import journal  # noqa: E402
from bii.forecast import gate, jr, report  # noqa: E402

FR = ROOT / "forecast"
mode = sys.argv[1] if len(sys.argv) > 1 else "claude"
now = datetime.now(timezone.utc)


def jload(p, default=None):
    try:
        return json.loads(Path(p).read_text())
    except (OSError, ValueError):
        return default


if mode == "risiko":
    from bii.forecast import lab as _lab
    for _ki in ("claude", "claude_offensiv"):
        _a = _lab.load_account(_ki)
        print(_lab.risk_analysis_text(_ki, *_a) if _a else f"# {_ki}: kein Konto")
    raise SystemExit(0)
wb = jload(FR / "wettbewerb.json", {})
started = wb.get("status") == "gestartet"
print(f"# Cockpit {now:%d.%m.%Y %H:%M} UTC\n")
if started:
    print(f"**Claude-Solo-Test ({wb.get('experiment')}):** Start **{wb['start']}** (Eröffnung {wb.get('start_eroeffnung_utc','')[:16].replace('T',' ')} UTC), letzter Kalendertag {wb.get('letzter_kalendertag','')}, Kapital {wb.get('kapital_eur', 10000):,.0f} € virtuell, Benchmark {wb['benchmark_instrument']['yahoo']}. Kein Echtgeld.\n")
    import pandas as _pd
    def _next(h, m, weekdays_only=True):
        t = _pd.Timestamp(now).tz_convert("UTC")
        for i in range(0, 9):
            c = (t + _pd.Timedelta(days=i)).replace(hour=h, minute=m, second=0, microsecond=0)
            if c > t and (not weekdays_only or c.weekday() < 5):
                return c.strftime("%a %d.%m. %H:%M UTC")
    print(f"**Nächste automatische Läufe:** Claude-Prognoseroutine {_next(9, 0)} · Orders einreichen {_next(12, 30)} · Datenlauf (Ausführung, Bewertung, Erfolgskontrolle) {_next(8, 0)} · Offensivkonto {_next(8, 20)} · Offensiv-Orders {_next(12, 45)}\n")
else:
    print("**Wettbewerb:** NICHT gestartet – bisher nur Pilotdaten, Konten unberührt (10.000 €)\n")
for ki in (("claude",) if mode == "claude" else jr.KIS):
    print(f"## {ki.capitalize()}\n")
    st = jload(FR / ki / "konto" / "state.json")
    if started and st:
        eq = st["equity"][-1] if st["equity"] else None
        print("### Portfolio (virtuell, nach Kosten)")
        if eq:
            print(f"Kontostand **{eq['aktiv_eur']:.2f} €** ({(eq['aktiv_eur']/st['kapital_eur']-1)*100:+.2f} %) · Benchmark {eq['bench_eur']:.2f} € ({(eq['bench_eur']/st['kapital_eur']-1)*100:+.2f} %) · Kosten {st['costs_eur']:.2f} € · Pause: {'JA' if st['paused'] else 'nein'}\n")
        rows = [f"| {t} | {p['stueck']} | {p['einstieg']} | {p['letzter_kurs']:.2f} | {(p['letzter_kurs']/p['einstieg']-1)*100:+.2f} % | {p['stop']} | {p['ziel']} |" for t, p in st["positions"].items()]
        if st.get("bench"):
            b = st["bench"]
            print(f"Benchmark-Portfolio: {b['stueck']} × {b['symbol']} gekauft am {b['datum']} zu {b['einstieg_eur']} € (Kosten {b['kosten_eur']} €), Restbargeld {b['cash_eur']} €.\n")
        elif st["last_date"] is None:
            print("Startsitzung noch nicht abgeschlossen – erster Kontostand und Benchmark-Kauf erscheinen nach dem nächsten Nachtlauf.\n")
        print("| Position | Stück | Einstieg | Kurs | G/V | Stop | Ziel |\n|---|---|---|---|---|---|---|\n" + ("\n".join(rows) if rows else "| – | | | | | | |") + "\n")
        if st["closed"]:
            print("Abgeschlossen:\n\n| Titel | G/V € | R | Grund |\n|---|---|---|---|\n" + "\n".join(f"| {c['ticker']} | {c['pnl_eur']:+.2f} | {c['r_multiple']:+.2f} | {c['grund']} |" for c in st["closed"][-8:]) + "\n")
    elif started:
        print("### Portfolio\nKonto eröffnet: 10.000,00 €, keine Positionen. Erster Tageszyklus nach der Startsitzung.\n")
    else:
        print("### Portfolio\nKein Wettbewerbskonto aktiv (Start steht aus). Kontostand 10.000,00 €, keine Positionen.\n")
    ps = journal.read(jr.path(ki)) if jr.path(ki).exists() else []
    last_day = max((p["erstellt_utc"][:10] for p in ps), default=None)
    print(f"### Aktuelle Einschätzungen und Kursprognosen (jüngster Prognosetag {last_day})")
    print(report.forecasts_table(ki, last_day) if last_day else "Noch keine Prognosen.\n")
    print("### Fällige / neue Bewertungen (letzte 10)\n")
    bs = journal.read(jr.path(ki, "bewertungen.jsonl")) if jr.path(ki, "bewertungen.jsonl").exists() else []
    print(report.evaluations_table(ki, bs[-10][ "erstellt_utc"] if len(bs) >= 10 else None) if bs else "Noch nichts fällig bzw. bewertet.\n")
    print("### Prognosegüte (getrennt von Trading)\n" + report.stats_table(ki, now.date()))
ops = jload(FR / "ops_status.json", {})
g = gate.evaluate_gate()
print("## Technischer Status\n")
print(f"- Letzte Erfolgskontrolle: {ops.get('lauf_utc','–')} · neue Bewertungen: {ops.get('neue_bewertungen','–')} · Datenprobleme: {len(ops.get('probleme', []))}")
wst = jload(FR / "wettbewerb_status.json", {})
print(f"- Wettbewerbszyklus: {wst.get('lauf_utc','noch nie gelaufen (nicht gestartet)')} · Probleme: {len(wst.get('probleme', []))}")
bm = jload(FR / "benchmark_entscheidung.json")
print(f"- Benchmark: {bm['symbol'] + ' (festgeschrieben ' + bm['festgeschrieben_utc'][:10] + ')' if bm else 'noch nicht festgeschrieben'}")
print(f"- Startschranke: {'ERFÜLLT' if g['alle_erfuellt'] else 'offen'}\n")
for k, v in g["bedingungen"].items():
    print(f"  - {'✔' if v['ok'] else '✘'} {k}: {v['detail']}")


# ------------------------------------------------------------------ Performance Lab (Haupt- und Offensivkonto nebeneinander)
from bii.forecast import lab  # noqa: E402

m_acc, o_acc = lab.load_account("claude"), lab.load_account("claude_offensiv")
mm = lab.metrics(*m_acc) if m_acc and m_acc[0]["equity"] else None
om = lab.metrics(*o_acc) if o_acc and o_acc[0]["equity"] else None
print("\n## Performance Lab – Hauptkonto (1 % Risiko) vs. Offensivkonto (2 % Risiko)\n")
if not o_acc:
    print("Offensivkonto ist noch nicht angelegt.\n")
else:
    ocfg = jload(FR / "offensiv" / "config.json", {})
    print(f"Offensivkonto: Start {ocfg.get('start')}, Regeln: 2 % Risiko je Trade, ≤ 6 % offenes Portfoliorisiko, ≤ 30 % je Instrument, Pause bei −15 %, kein Hebel/keine Leerverkäufe.\n")
    f = lambda m, k, fmt, dash="–": dash if not m or m.get(k) is None else format(m[k], fmt)  # noqa: E731
    mixp = lab.mix_pct()
    rows = [("Kontostand €", "stand", ".2f"), ("Gewinn/Verlust €", "pnl_eur", "+.2f"), ("Gewinn/Verlust %", "pnl_pct", "+.2f"), ("Max. Rückgang %", "maxdd_pct", ".2f"),
            ("Volatilität p.a. %", "vol_ann_pct", ".1f"), ("Abgeschl. Trades", "trades", "d"), ("Trefferquote Trades %", "treffer", ".0f"), ("Offene Positionen", "offen", "d"),
            ("Kosten €", "kosten_eur", ".2f"), ("Gewinn je 1 € geplantem Risiko", "gewinn_je_risiko", "+.2f"), ("Offenes geplantes Risiko €", "offenes_risiko_eur", ".0f"),
            ("Stressverlust €* ", "stress_verlust_eur", ".0f"), ("Schlechtester Trade in Vielfachen des geplanten Risikos", "schlechtester_trade_in_risiko", "+.2f")]
    print("| Kennzahl | Hauptkonto | Offensiv |\n|---|---|---|")
    for name, k, fmt in rows:
        print(f"| {name} | {f(mm, k, fmt)} | {f(om, k, fmt)} |")
    print(f"| Pause aktiv | {mm['pausiert'] if mm else '–'} | {om['pausiert'] if om else '–'} |")
    ref = om or mm
    print(f"| EUNL (Benchmark) % | {f(mm, 'bench_pct', '+.2f')} | {f(om, 'bench_pct', '+.2f')} |")
    print(f"| Passiver Mix % (60 % EUNL / 30 % Gold / 10 % Bargeld) | {'–' if mixp is None else format(mixp, '+.2f')} | {'–' if mixp is None else format(mixp, '+.2f')} |")
    print("\n*Stressverlust = alle Stops werden zusätzlich 3 % durchlaufen (Kurslücken). Stopkurse sind keine garantierte Verlustgrenze.")
    if om:
        print(f"\n**Zielmarke Offensivkonto (nach Kosten, 60 Tage):** {lab.ziel_label(om['pnl_pct'])} – experimentell, kein Versprechen.")
    print("\n**Chancenwahl oder nur mehr Risiko?** " + lab.verdict(mm, om, lab.attribution(m_acc, o_acc)) + "\n")
    for nm, acc in (("Hauptkonto", m_acc), ("Offensiv", o_acc)):
        if acc and acc[0]["paused"]:
            print(f"⚠️ {nm}: neue Positionen pausiert (Drawdown-Grenze). Vollständige Risikoanalyse siehe `python scripts/fc_cockpit.py risiko`.")
