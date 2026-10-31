"""Heartbeat: Sind die geplanten Läufe frisch genug? Exit 1 + heartbeat.txt bei Ausfall.

Grenzwerte orientieren sich am Zeitplan (nicht an Echtzeit):
- Marktcheck (Mo–Fr 18:40 Berlin): letzter Lauf höchstens 4 Tage alt (überbrückt Wochenende + Feiertag)
- Research-Monitor (bis zu 4 Läufe/Tag): letzter erfolgreicher Lauf höchstens 30 Stunden alt
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKS = [
    ("Marktcheck FT1", ROOT / "journal" / "ops_status.json", "letzter_lauf_utc", timedelta(days=4)),
    ("Research-Monitor", ROOT / "research" / "desk" / "state" / "monitor_status.json", "letzter_erfolg_utc", timedelta(hours=30)),
]


def check(now: datetime | None = None) -> list[str]:
    now = now or datetime.now(timezone.utc)
    problems = []
    for name, path, field, limit in CHECKS:
        if not path.exists():
            problems.append(f"{name}: Statusdatei fehlt ({path.relative_to(ROOT)})")
            continue
        ts = json.loads(path.read_text()).get(field)
        if not ts:
            problems.append(f"{name}: kein Zeitstempel '{field}'")
            continue
        age = now - datetime.fromisoformat(ts)
        if age > limit:
            problems.append(f"{name}: letzter Lauf {ts} ist {age.total_seconds() / 3600:.0f} h alt (Grenze {limit.total_seconds() / 3600:.0f} h)")
    return problems


if __name__ == "__main__":
    p = check()
    msg = "\n".join(p) if p else "Alle Läufe frisch."
    print(msg)
    if p:
        (ROOT / "heartbeat.txt").write_text(msg + "\n")
    sys.exit(1 if p else 0)
