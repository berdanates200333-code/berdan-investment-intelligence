#!/usr/bin/env bash
# Sicherer Push der Routine: Remote-Stand vor dem Commit aktualisieren (Rebase), Push über HEAD:Branch, danach Remote-HEAD == lokalem HEAD prüfen.
set -euo pipefail
BR=claude/phase1-grundsystem
MSG="${1:-Claude-Prognosen}"
git add forecast/claude
if git diff --cached --quiet; then echo "PUSH: nichts zu committen"; exit 0; fi
git commit -q -m "$MSG

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
for i in 1 2 3 4; do
  git fetch -q origin "$BR"
  git rebase -q --autostash "origin/$BR" && git push -q origin "HEAD:$BR" && break || { echo "PUSH: Versuch $i fehlgeschlagen"; sleep $((i*3)); }
done
git fetch -q origin "$BR"
[ "$(git rev-parse HEAD)" = "$(git ls-remote origin refs/heads/$BR | cut -f1)" ] && echo "PUSH-OK: $(git rev-parse --short HEAD)" || { echo "PUSH-FEHLER: Remote-HEAD weicht ab"; exit 5; }
