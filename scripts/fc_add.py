"""Prognose ins Journal einer KI aufnehmen. Aufruf: python scripts/fc_add.py <ki> <datei.json> [--manuell]
--manuell: Prognose wurde vom Nutzer übertragen (z. B. ChatGPT); Zeitstempel = Eingang im Journal, Originalzeitpunkt nur behauptet."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bii.forecast import jr  # noqa: E402

ki, f = sys.argv[1], sys.argv[2]
data = json.loads(Path(f).read_text())
for p in (data if isinstance(data, list) else [data]):
    p["ki"] = ki
    if "--manuell" in sys.argv:
        p["uebertragen_durch_nutzer"] = True
    e = jr.add(p)
    print("aufgenommen:", e["prognose_id"], e["erstellt_utc"])
