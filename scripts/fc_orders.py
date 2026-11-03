"""Vor der US-Eröffnung (Workflow forecast-orders.yml): neue KAUFEN-Prognosen als dokumentierte virtuelle Orders einreichen (nur nach Start)."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bii.forecast import live, wettbewerb  # noqa: E402

now = datetime.now(timezone.utc)
res = wettbewerb.submit_orders_only(live.Live(now, "2y"), now)
(ROOT / "forecast" / "orders_status.json").write_text(json.dumps({"lauf_utc": now.isoformat(timespec="seconds"), **res}, indent=1, ensure_ascii=False))
print(json.dumps(res, ensure_ascii=False)[:1200])
raise SystemExit(2 if res.get("probleme") else 0)
