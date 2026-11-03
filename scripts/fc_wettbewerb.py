"""Täglicher Wettbewerbszyklus der echten KI-Konten (nur nach offiziellem Start). Exit 2 bei Datenfehlern/Kontenabweichung."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bii.forecast import live, wettbewerb  # noqa: E402

now = datetime.now(timezone.utc)
res = wettbewerb.run_daily(live.Live(now, "2y"), now)
(ROOT / "forecast" / "wettbewerb_status.json").write_text(json.dumps({"lauf_utc": now.isoformat(timespec="seconds"), **res}, indent=1, ensure_ascii=False))
print(json.dumps(res, ensure_ascii=False)[:1500])
raise SystemExit(2 if res.get("probleme") else 0)
