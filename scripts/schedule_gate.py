"""Zeitplan-Weiche: Soll dieser Workflow-Lauf den Marktcheck ausführen?

GitHub-Zeitpläne laufen in UTC. Zwei Cron-Einträge (16:40 und 17:40 UTC) decken 18:40 Uhr
Europe/Berlin in Sommer- (UTC+2) und Winterzeit (UTC+1) ab. Diese Weiche lässt nur den Eintrag
durch, der am aktuellen Tag 18:40 Uhr Berliner Ortszeit entspricht. Maßgeblich ist die
GEPLANTE Uhrzeit (Cron-Ausdruck), nicht die tatsächliche Startzeit – GitHub startet geplante
Läufe oft mit Verzögerung.

Aufruf im Workflow: python scripts/schedule_gate.py "<event_name>" "<cron>" -> schreibt run=true|false
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
BERLIN = ZoneInfo("Europe/Berlin")
TARGET = (18, 40)


def decide(event: str, cron: str, now_utc: datetime, last_scheduled_date: str | None) -> tuple[bool, str]:
    if event != "schedule":
        return True, f"manueller Start ({event})"
    minute, hour = (int(x) for x in cron.split()[:2])
    planned_utc = now_utc.replace(hour=hour, minute=minute, second=0, microsecond=0)
    planned_local = planned_utc.astimezone(BERLIN)
    if (planned_local.hour, planned_local.minute) != TARGET:
        return False, f"Cron {hour:02d}:{minute:02d} UTC = {planned_local:%H:%M} Uhr Berlin – nicht der 18:40-Slot"
    if planned_local.weekday() >= 5:
        return False, "Wochenende in Berlin"
    if last_scheduled_date == planned_local.date().isoformat():
        return False, "heute bereits planmäßig gelaufen"
    return True, f"planmäßiger Lauf {planned_local:%d.%m.%Y %H:%M} Uhr Berlin"


def main() -> int:
    event, cron = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else "")
    ops = ROOT / "journal" / "ops_status.json"
    last = json.loads(ops.read_text()).get("letzter_planlauf_datum") if ops.exists() else None
    now = datetime.now(timezone.utc)
    run, why = decide(event, cron, now, last)
    print(f"run={run}: {why}")
    if run and event == "schedule":
        d = json.loads(ops.read_text()) if ops.exists() else {}
        d["letzter_planlauf_datum"] = now.astimezone(BERLIN).date().isoformat()
        ops.write_text(json.dumps(d, indent=2, ensure_ascii=False))
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a") as f:
            f.write(f"run={'true' if run else 'false'}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
