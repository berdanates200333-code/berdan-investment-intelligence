"""Chat-Bericht (Markdown). Prognosegüte und Tradingperformance werden GETRENNT ausgewiesen.
Aufruf: python scripts/fc_report.py claude|vergleich   ('vergleich' liest beide Journale – nicht vor der eigenen Tagesprognose verwenden)"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bii import journal  # noqa: E402
from bii.forecast import jr, report  # noqa: E402

today = datetime.now(timezone.utc).date()
mode = sys.argv[1] if len(sys.argv) > 1 else "claude"
for ki in (("claude",) if mode == "claude" else jr.KIS):
    ok, msg = journal.verify(jr.path(ki))
    print(f"## {ki.upper()} – Prognosejournal: {msg}\n\n### Prognosegüte\n{report.stats_table(ki, today)}\n### Bewertungen\n{report.evaluations_table(ki)}")
    sp = ROOT / "forecast" / ki / "konto" / "state.json"
    if sp.exists():
        st = json.loads(sp.read_text())
        eq = st["equity"][-1]["aktiv_eur"] if st["equity"] else st["kapital_eur"]
        print(f"### Trading (separat, nach Kosten)\nKontostand {eq:.2f} € · Kosten {st['costs_eur']:.2f} € · offene Positionen {len(st['positions'])} · abgeschlossene Trades {len(st['closed'])}\n")
    else:
        print("### Trading (separat)\nKonto noch nicht gestartet (Wettbewerb nicht gestartet).\n")
