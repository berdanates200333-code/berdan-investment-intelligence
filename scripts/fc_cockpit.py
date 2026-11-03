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
    print(f"**Nächste automatische Läufe:** Claude-Prognoseroutine {_next(23, 40)} · Orders einreichen {_next(12, 30)} · Nachtlauf (Ausführung, Bewertung, Erfolgskontrolle) {_next(23, 0)}\n")
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
