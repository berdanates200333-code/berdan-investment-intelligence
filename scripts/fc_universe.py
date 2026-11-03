"""Universum live prüfen (Datenstufe A + Liquidität) und Status schreiben."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bii.forecast import live, universe  # noqa: E402

now = datetime.now(timezone.utc)
lv = live.Live(now, "2y")
st = universe.check_universe(lv, now)
st["probleme"] = lv.log
st["abrufe"] = lv.requests
universe.STATUS.write_text(json.dumps(st, indent=1, ensure_ascii=False))
n = sum(v["zugelassen"] for v in st["instrumente"].values())
print(f"zugelassen: {n}/{len(st['instrumente'])}")
for k, v in st["instrumente"].items():
    if not v["zugelassen"]:
        print("nicht zugelassen:", k, v["stufe"], v.get("gruende") or v.get("grund"))
