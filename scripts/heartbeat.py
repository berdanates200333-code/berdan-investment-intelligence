"""Heartbeat: Prüft, ob Marktcheck und Research-Monitor zuletzt rechtzeitig gelaufen sind.

Aufruf: python scripts/heartbeat.py  -> Exit 0 = alles frisch, Exit 2 = veraltet (Meldung auf stdout)
Wird von GitHub Actions (heartbeat.yml) UND unabhängig davon von einer Claude-Aufgabe genutzt.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Höchstalter in Stunden: Marktcheck läuft nur Mo–Fr (Wochenende + Verzögerung -> 76 h)
CHECKS = {
    "Marktcheck FT1": (ROOT / "journal" / "ops_status.json", "letzter_lauf_utc", 76),
    "Paper-Trading": (ROOT / "papertrading" / "ops_status.json", "letzter_lauf_utc", 76),
    "Research-Monitor": (ROOT / "research" / "db" / "ops.json", "letzter_lauf_utc", 14),
    "Research-Monitor (erfolgreicher Datenabruf)": (ROOT / "research" / "db" / "ops.json", "letzter_erfolg_utc", 30),
}


def check(now: datetime | None = None) -> list[str]:
    now = now or datetime.now(timezone.utc)
    problems = []
    for name, (path, key, max_h) in CHECKS.items():
        if not path.exists():
            problems.append(f"{name}: Statusdatei fehlt ({path.relative_to(ROOT)})")
            continue
        ts = json.loads(path.read_text()).get(key)
        if not ts:
            problems.append(f"{name}: kein Zeitstempel '{key}'")
            continue
        age = (now - datetime.fromisoformat(ts)).total_seconds() / 3600
        if age > max_h:
            problems.append(f"{name}: letzter Lauf vor {age:.0f} h (Grenze {max_h} h)")
    return problems


if __name__ == "__main__":
    p = check()
    print("OK – alle Überwachungen frisch" if not p else "\n".join(p))
    sys.exit(2 if p else 0)
