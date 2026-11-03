"""Eingangsdienst für versiegelte Prognosen (läuft in GitHub Actions, unbeaufsichtigt):
 1. Einmal-Schlüsselpaar erzeugen, nur den öffentlichen Schlüssel committen (forecast/intake/<sitzung>/pubkey.pem).
 2. Bis zum Cutoff Chiffrate (forecast/inbox/<ki>/<sitzung>/sealed.json) annehmen und mit Serverzeit belegen.
 3. Nach dem Cutoff entschlüsseln, ins Prognosejournal übernehmen, Beleg schreiben, committen. Privater Schlüssel verschwindet mit dem Lauf."""
from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pandas as pd  # noqa: E402

from bii.forecast import calendars, commitreveal as cr, jr, sealed  # noqa: E402


def git(*a):
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True)


def publish(msg):
    git("config", "user.name", "market-check-bot")
    git("config", "user.email", "actions@users.noreply.github.com")
    git("add", "forecast")
    if git("diff", "--cached", "--quiet").returncode == 0:
        return
    git("commit", "-q", "-m", msg)
    for _ in range(4):
        if git("pull", "-q", "--rebase", "origin", "claude/phase1-grundsystem").returncode == 0 and git("push", "-q", "origin", "HEAD:claude/phase1-grundsystem").returncode == 0:
            return
        time.sleep(5)
    raise SystemExit("Push fehlgeschlagen")


def main() -> int:
    now = datetime.now(timezone.utc)
    day, opening = calendars.next_session_open("XNYS", now)
    sitzung, cutoff = str(day.date()), opening - cr.COMMIT_LEAD
    if (cutoff - pd.Timestamp(now)) > pd.Timedelta(hours=2.5):
        print("Nächste Sitzung noch weit entfernt – nichts zu tun.")
        return 0
    priv, pub = sealed.new_keypair()
    pk = ROOT / "forecast" / "intake" / sitzung / "pubkey.pem"
    pk.parent.mkdir(parents=True, exist_ok=True)
    if pk.exists():
        print("Für diese Sitzung existiert schon ein Schlüssel – Lauf beendet (kein zweites Schlüsselpaar).")
        return 0
    pk.write_text(pub)
    publish(f"Eingang {sitzung}: Einmal-Schlüssel (öffentlich)")
    seen = set()
    while pd.Timestamp(datetime.now(timezone.utc)) < cutoff:
        git("pull", "-q", "--rebase", "origin", "claude/phase1-grundsystem")
        for ki in jr.KIS:
            f = ROOT / "forecast" / "inbox" / ki / sitzung / "sealed.json"
            if f.exists() and ki not in seen:
                try:
                    cr.seal_accept(ki, sitzung, json.loads(f.read_text()), datetime.now(timezone.utc))
                    seen.add(ki)
                    print("Chiffrat angenommen:", ki)
                except Exception as e:  # noqa: BLE001
                    print("abgelehnt:", ki, e)
        publish(f"Eingang {sitzung}: Belege")
        time.sleep(30)
    while pd.Timestamp(datetime.now(timezone.utc)) < cutoff:        # Sicherheit gegen Uhrabweichung
        time.sleep(2)
    for ki in sorted(seen):
        try:
            cr.seal_reveal(ki, sitzung, json.loads((ROOT / "forecast" / "inbox" / ki / sitzung / "sealed.json").read_text()), priv, datetime.now(timezone.utc))
            print("übernommen:", ki)
        except Exception as e:  # noqa: BLE001
            rej = ROOT / "forecast" / "receipts" / ki / f"{sitzung}.reveal.abgelehnt.json"
            rej.parent.mkdir(parents=True, exist_ok=True)
            rej.write_text(json.dumps({"ki": ki, "sitzung": sitzung, "grund": str(e)}, ensure_ascii=False))
            print("ABGELEHNT beim Entschlüsseln:", ki, e)
    publish(f"Eingang {sitzung}: Prognosen übernommen")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
