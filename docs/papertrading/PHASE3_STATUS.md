# Phase 3 – Paper-Trading: Umsetzung, Prüfergebnisse, Autonomiestatus (Stand 02.11.2026)

## Ist das vorhandene Kurs- und Nachrichtensystem ausreichend?
- **Swing-Trading (Tagesdaten): ja, mit Einschränkungen.** Yahoo-Tagesbalken (OHLCV), Stooq-Gegenprüfung, EZB-Kurse und Google-News-RSS reichen für tägliche Entscheidungen und die Simulation von Eröffnungs-/Stop-/Zielausführungen. Einschränkungen: inoffizielle Quellen können ausfallen; Zweitquelle/Nachrichten sind nicht immer erreichbar (wird als „ungeprüft“ protokolliert); Nachrichten nur Schlagzeilen-Metadaten.
- **Intraday: nein.** Es gibt keine Intraday-Kurse, Orderbuch- oder Spreaddaten und keine Ausführungssimulation dafür. Intraday-Handel ist nicht implementiert.
- **Fundamentalanalyse:** nur für die 3 Unternehmen des Research-Desks (Profile/Thesen) vorhanden. Für das übrige Universum fehlt eine automatische Fundamentalprüfung (Qualität wird nur über die Universumsauswahl und technische Liquiditätsfilter angenähert). Optional ergänzt Claude Vetos (`/papertrading-review`).

## Umsetzung der Risikogrenzen (geprüft durch Tests in `tests/test_papertrading.py`)
| Vorgabe | Umsetzung | Test |
|---|---|---|
| ≤ 1 % geplantes Risiko je Trade | Stückzahl aus Risikobudget (inkl. aller Kosten, ab Kauflimit); Kurslücken über dem Stop können den realen Verlust übersteigen (Gap-Risiko, dokumentiert) | `test_plan_documented_before_execution_and_risk_limit`, `test_sizing_respects_budget_and_cash`, `test_stop_gap_fills_at_open_and_closes_trade` |
| Kein Hebel / keine Kredite | Kosten ≤ freie Barmittel, keine Shorts | `test_execution_costs_and_no_leverage` |
| Pause bei −10 % | Prüfung am Tagesende gegen Höchststand, Pause nur per Freigabe aufhebbar | `test_drawdown_pause_blocks_new_positions` |
| Order vor Ausführung dokumentiert | Journal-Eintrag vor Simulation; zu spät dokumentierte Pläne verworfen | `test_plan_documented_before_execution…`, `test_late_documented_plan_rejected` |
| Nur damals verfügbare Daten | Signale schneiden Daten auf Tag d ab; unvollständige Tagesbalken ignoriert | `test_no_lookahead_in_signal`, `test_incomplete_day_not_processed` |
| Fehlgeschlagene Ausführung | Limit-Gap, Stop-Unterschreitung, Ablehnung, fehlende Daten | `test_gap_above_limit_fails`, `test_data_failure_blocks_trading` |
| FT1 unverändert | Paper-Trading schreibt nur in eigene Ordner | `test_ft1_journal_untouched_by_papertrading`, `tests/test_journal_pins.py` |
| Regeln eingefroren | SHA-256-Pin der Regeldatei | `test_rules_file_pinned` |

## Was läuft autonom (GitHub Actions, kostenlos)?
| Aufgabe | Status |
|---|---|
| Tageslauf Mo–Fr 22:30 UTC: Daten, Signale, Orderpläne, Ausführungssimulation, Exits, Benchmark, Pause, Journal, Tagesstand (`papertrading-daily.yml`) | **eingerichtet, noch nicht live bewiesen** (siehe unten) |
| Wochenbericht Sonntag 09:00 UTC + GitHub-Issue als Benachrichtigung (`papertrading-weekly.yml`) | eingerichtet, noch nicht live gelaufen |
| Abschlussbewertung nach 24.01.2027 und automatische 4-Wochen-Verlängerung bei zu kleiner Stichprobe | im Wochen-Workflow enthalten, nur mit synthetischen Daten getestet |
| Heartbeat-Prüfung des Paper-Trading-Laufs (`scripts/heartbeat.py`) | eingerichtet |
| Technische Fehler → GitHub-Issue | eingerichtet |

## Was läuft noch NICHT autonom / ist offen?
- **Live-Datenabruf nicht verifiziert:** In der Entwicklungsumgebung war das Netz gesperrt; Yahoo/Stooq/EZB/Google-News-Abrufe sind nur über Fehlerbehandlung und Tests mit synthetischen Daten abgesichert. Der erste echte Lauf (Workflow „Paper-Trading täglich“, manuell startbar) muss geprüft werden; bei Pflichtdatenausfall entsteht ein Fehler-Issue statt Trades.
- **Claude-Analyse im Takt nicht geplant:** `/papertrading-review` (qualitatives Veto/Notizen, siehe `.claude/commands/papertrading-review.md`) ist als Befehl vorhanden, aber noch nicht als geplante Aufgabe eingerichtet. Ohne sie handelt v1.0 rein regelbasiert (Nachrichten-Schlagwort-Veto statt KI-Lesen).
- Fundamentale Unternehmensanalyse für das Gesamtuniversum, Earnings-Kalender (nur Ereignistag-Filter), Steuerberechnung, Intraday: nicht vorhanden.
- Pausenfreigabe und Strategieänderungen bleiben manuelle Entscheidungen.
- GitHub-Zeitpläne können verzögert starten; verpasste Tage werden beim nächsten Lauf nachverarbeitet (ohne neue Pläne für alte Tage).

## Versionierung
`papertrading/registry.json` führt Versionen mit Regeldatei-Hash. Neue Regeln = neue Datei + neuer Ordner + eigener, prospektiver Teststart; v1.0 bleibt unverändert.
