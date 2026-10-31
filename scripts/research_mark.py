"""Analyseauftrag abschließen: Status im Ereignisspeicher anhängen und Auftrag ablegen.

Aufruf: python scripts/research_mark.py <ereignis_id> <status> [analyse_pfad]
Status: analysiert | verworfen | zurueckgestellt
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bii.research.events import Store  # noqa: E402


def main(eid: str, status: str, path: str = "") -> int:
    if status not in ("analysiert", "verworfen", "zurueckgestellt"):
        raise SystemExit("Status muss analysiert|verworfen|zurueckgestellt sein")
    s = Store()
    if eid not in s.ids:
        raise SystemExit(f"Unbekanntes Ereignis {eid}")
    s.set_status(eid, status, path)
    q = ROOT / "research" / "queue" / (re.sub(r"[^A-Za-z0-9_-]", "_", eid) + ".json")
    if q.exists():
        d = json.loads(q.read_text())
        d.update({"status": status, "analyse": path})
        dest = q.parent / "erledigt" / q.name
        dest.parent.mkdir(exist_ok=True)
        dest.write_text(json.dumps(d, indent=2, ensure_ascii=False))
        q.unlink()
    print(f"{eid}: {status}")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
