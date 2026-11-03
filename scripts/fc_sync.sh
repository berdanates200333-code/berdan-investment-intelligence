#!/usr/bin/env bash
# Verbindlicher Sync für die tägliche Claude-Routine: checkt den AKTUELLEN Remote-Stand aus, gleicht ihn mit dem Remote-HEAD ab
# und prüft, dass der Solo-Test gestartet ist. Exit != 0 => Routine bricht ab (keine Prognosen auf altem Stand).
set -euo pipefail
BR=claude/phase1-grundsystem
git fetch origin "$BR"
git checkout -q -B "$BR" "origin/$BR"                     # auch bei detached HEAD / altem lokalem Branch
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git ls-remote origin "refs/heads/$BR" | cut -f1)
if [ "$LOCAL" != "$REMOTE" ]; then echo "SYNC-FEHLER: lokal $LOCAL != remote $REMOTE"; exit 3; fi
python3 - <<'PY'
import json, sys
d = json.load(open("forecast/wettbewerb.json"))
if d.get("status") != "gestartet" or d.get("modus") != "solo":
    print("SYNC-FEHLER: wettbewerb.json zeigt", d.get("status"), d.get("modus")); sys.exit(4)
print("SYNC-OK: HEAD", __import__("subprocess").check_output(["git","rev-parse","--short","HEAD"],text=True).strip(), "| Solo gestartet, Start", d["start"], "| Ende exkl.", d["ende_exklusiv"])
PY
echo "HEAD=$LOCAL"
git log -1 --format='%h %an %s'
