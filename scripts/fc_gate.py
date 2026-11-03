"""Startbedingungen prüfen und dokumentieren. 'python scripts/fc_gate.py' schreibt forecast/wettbewerb_gate.json (Status nicht_gestartet).
Start nur explizit: 'python scripts/fc_gate.py --start' (verweigert, solange Bedingungen fehlen)."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bii.forecast import gate  # noqa: E402

if "--start" in sys.argv:
    doc = gate.start(datetime.now(timezone.utc))
    (ROOT / "forecast" / "wettbewerb.json").write_text(json.dumps(doc, indent=1, ensure_ascii=False))
    print("GESTARTET", doc["start"])
else:
    g = gate.evaluate_gate()
    (ROOT / "forecast" / "wettbewerb_gate.json").write_text(json.dumps({"status": "nicht_gestartet" if not g["alle_erfuellt"] else "startbereit", **g}, indent=1, ensure_ascii=False))
    for k, v in g["bedingungen"].items():
        print(("OK   " if v["ok"] else "FEHLT"), k, "-", v["detail"])
