---
description: Tägliche Claude-Prognose per Commit-Reveal (blind, nur virtuell) – erst nach Wettbewerbsstart einplanen
---
Du bist Claude im Prognosewettbewerb. Deutsch, nur virtuell, keine Echtgeldorders. **Lies niemals `forecast/chatgpt/`, `forecast/receipts/chatgpt/`, `forecast/inbox/chatgpt/` oder Vergleichsberichte, bevor dein Commit für die Sitzung abgelegt ist.**
1. `git pull`. Lies `forecast/universum_status.json` (nur zugelassene Instrumente, Datenstufe A) und `forecast/ops_status.json`.
2. Prüfe die Sitzung mit `python -c "from bii.forecast import commitreveal as c; print(c.windows('XNYS', __import__('datetime').datetime.now(__import__('datetime').timezone.utc)))"`: Commit nur vor `cutoff_utc`.
3. Erzeuge 3–5 Prognosen (Schema `docs/forecast/PROGNOSESYSTEM.md`), Referenz = letzter abgeschlossener Handelstag (Datenstufe A), Zieltermine per `calendars.horizon_dates`. Erfinde keine Zahlen; unzureichende Daten → `belastbarkeit: nicht_belastbar`.
4. Lege `commitreveal.commitment(prognosen, nonce)` als `forecast/inbox/claude/<sitzung>/commit.json` ({"hash": ...}) ab, pushe. Nach dem Cutoff (und vor der Eröffnung) lege `reveal.json` ({"prognosen": [...], "nonce": "..."}) ab, pushe. Den Rest erledigt der Dienst `forecast-intake`.
5. Kaufentscheidungen: nur Wettbewerbsphase; Order über `ai_portfolio.submit_order` (Positionsgröße bestimmt die gemeinsame Risikoregel).
