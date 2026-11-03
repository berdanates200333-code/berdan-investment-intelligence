"""Offensivkonto: init | cycle | orders. Läuft getrennt vom Hauptkonto; Fehler hier berühren das Hauptkonto nicht."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bii.forecast import live, offensiv  # noqa: E402

mode = sys.argv[1] if len(sys.argv) > 1 else "cycle"
now = datetime.now(timezone.utc)
if mode == "init":
    cfg = offensiv.init(now)
    print("OFFENSIVKONTO ANGELEGT: Start", cfg["start"], "Ende exkl.", cfg["ende_exklusiv"], cfg["parameter"])
    raise SystemExit(0)
lv = live.Live(now, "2y")
res = offensiv.run_cycle(lv, now) if mode == "cycle" else offensiv.submit_orders(lv, now)
(ROOT / "forecast" / f"offensiv_{mode}_status.json").write_text(json.dumps({"lauf_utc": now.isoformat(timespec="seconds"), **res}, indent=1, ensure_ascii=False))
print(json.dumps(res, ensure_ascii=False)[:1000])
raise SystemExit(2 if res.get("probleme") else 0)
