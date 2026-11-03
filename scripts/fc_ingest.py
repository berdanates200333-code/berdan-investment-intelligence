"""Eingangsdienst (GitHub Actions): verarbeitet neue Dateien unter forecast/inbox/<ki>/<sitzung>/{commit,reveal}.json.
Zeitstempel = Serverzeit dieses Laufs. Verstöße werden in forecast/receipts/<ki>/<sitzung>.abgelehnt.json protokolliert (kein Überschreiben)."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bii.forecast import commitreveal as cr, jr  # noqa: E402


def main() -> int:
    now = datetime.now(timezone.utc)
    event = os.environ.get("GITHUB_EVENT_NAME", "lokal")
    rc = 0
    for ki in jr.KIS:
        for sdir in sorted((ROOT / "forecast" / "inbox" / ki).glob("*")) if (ROOT / "forecast" / "inbox" / ki).exists() else []:
            for stage in ("commit", "reveal"):
                f = sdir / f"{stage}.json"
                done = cr.receipt_path(ki, sdir.name, stage)
                rej = ROOT / "forecast" / "receipts" / ki / f"{sdir.name}.{stage}.abgelehnt.json"
                if not f.exists() or done.exists() or rej.exists():
                    continue
                try:
                    r = cr.ingest(ki, sdir.name, stage, json.loads(f.read_text()), now, event)
                    print("angenommen:", ki, sdir.name, stage, r["server_utc"])
                except Exception as e:  # noqa: BLE001
                    rej.parent.mkdir(parents=True, exist_ok=True)
                    rej.write_text(json.dumps({"ki": ki, "sitzung": sdir.name, "stage": stage, "grund": str(e), "server_utc": now.isoformat(timespec="seconds")}, ensure_ascii=False, indent=1))
                    print("ABGELEHNT:", ki, sdir.name, stage, e)
                    rc = 0   # Ablehnung ist ein dokumentiertes Ergebnis, kein Systemfehler
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
