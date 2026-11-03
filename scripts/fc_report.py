"""Chat-Bericht (Markdown) ausgeben. Aufruf: python scripts/fc_report.py claude|vergleich"""
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bii import journal  # noqa: E402
from bii.forecast import jr, portfolio, report  # noqa: E402

today = datetime.now(timezone.utc).date()
mode = sys.argv[1] if len(sys.argv) > 1 else "claude"
kis = ("claude",) if mode == "claude" else jr.KIS
for ki in kis:
    ok, msg = journal.verify(jr.path(ki))
    print(f"## {ki.upper()} – Prognosejournal: {msg}\n\n{report.stats_table(ki, today)}")
    print(f"Bewertungen:\n\n{report.evaluations_table(ki)}")
    st = portfolio.state(ki)
    print(f"Portfolio (nur Bargeld/Positionen aus Journal): Bargeld {st['cash_eur']:.2f} €, Positionen {list(st['positionen']) or 'keine'}\n")
