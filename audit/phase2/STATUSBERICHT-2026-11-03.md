# BERDAN INVESTMENT INTELLIGENCE – technischer Status zum Gegencheck

Stand: 2026-11-03, 07:16 UTC. Dieser Bericht ersetzt die aktuellen Statusaussagen des Übernahmeberichts vom 2. November. Dessen ursprüngliche Datei und Strategieunterlagen bleiben als historische Dokumente unverändert. **Verbindlich sind 60 Kalendertage, nicht 30 Tage.**

## Ergebnis

**Die Absicherung und Veröffentlichung sind nachgewiesen; ein vollständiger produktiver Paper-Trading-Start ist weiterhin NICHT nachgewiesen.** Zwei echte Datenläufe, davon einer mit dem virtuellen Ausführungsschalter, wurden aufgrund eines ungültigen EUNL-Schlusskurses ordnungsgemäß abgewiesen. Es gibt keinen Startzeitpunkt, kein Abschlussdatum, keine neu simulierten Ausführungen und keine Echtgeldfreigabe.

- Repository: https://github.com/berdanates200333-code/berdan-investment-intelligence
- Standardbranch: `claude/phase1-grundsystem`; geprüfter Bestand `db9bf5a`.
- Sicherheitskorrekturen: separater **PR #9**, offen: https://github.com/berdanates200333-code/berdan-investment-intelligence/pull/9
- Neue 60-Tage-Implementierung: **Draft PR #10**, baut auf PR #9 auf: https://github.com/berdanates200333-code/berdan-investment-intelligence/pull/10
- PR #10 zielt zunächst auf `codex/papertrading-safety`. Nach Übernahme von #9 muss #10 auf den Standardbranch umgestellt und erneut geprüft werden. Kein automatischer Merge und keine produktive Ausführung wurden behauptet.

## Nachgewiesen funktionsfähig

1. **Safety Hold im Standardbranch:** täglicher und wöchentlicher Legacy-Paper-Workflow haben keinen Zeitplan mehr und der jeweilige Job ist mit `if: false` gesperrt. FT1 und Research-Monitor bleiben aktiv. GitHub führt die Workflowdateien weiterhin als „active“; maßgeblich ist die tatsächliche Jobsperre.
2. **Authentifizierter GitHub-App-Zugriff:** Repository-Rechte `admin`, `maintain`, `pull`, `push`, `triage` gemeldet; neuer Branch und neue Dateien tatsächlich geschrieben, PR #10 erstellt. Shell-`git push --dry-run` scheitert weiterhin mangels Git-Anmeldung. Keine Zugangsdaten ausgegeben oder im Code gespeichert.
3. **Reproduzierbare lokale Installation:** Python 3.12.14; exakt gepinnte Pakete aus `requirements-pt60.lock` in frischer virtueller Umgebung installiert.
4. **76/76 Tests bestanden:** 56 vorhandene Sicherheits-/Bestandstests plus 20 neue Prüffälle. JUnit und Konsolenausgabe liegen bei. Auch der GitHub-PR-Prüflauf am Implementierungsstand `da2121322a2300bf614ce3ade36a2438dc1f28d4` ist erfolgreich: https://github.com/berdanates200333-code/berdan-investment-intelligence/actions/runs/41594676038 . Die PR-Prüfung führt Tests aus; Live-Preflight und Research sind bei PR-Ereignissen absichtlich ausgenommen. Acht Deprecation-Warnungen betreffen den Kalender-/Pandas-Unterbau, keine Testfehler.
5. **Bestandsschutz:** 69 bestehende Dateien unter Journalen, Daten, Research, Paper-Trading, Dokumentation sowie die Signaldatei wurden bytegenau gegen den geprüften Remote-Bestand abgeglichen. Keine Abweichung. SHA-256 der Signalregeln v1.0 weiterhin `43b29a9918f72dc35e2de0beb7f5a4fa33a01cc1d458639880b6ade0ce0eeb0d`.
6. **Realer Teil-Datenpfad:** In beiden Läufen 64 archivierte HTTP-Antworten: 32 Yahoo-Reihen, 31 Nasdaq-Gegenprüfungen, eine EZB-Reihe. 30 US-Aktien und SPY bestanden die implementierte OHLC-Gegenprüfung; EUR/USD konnte verarbeitet werden. Das ist ein erfolgreicher Teilpfad, kein vollständiger Handelserfolg.
7. **Research-Intake im isolierten Ordner:** realer Abruf erreicht 30/30 Aktien, erfasst 2.051 initiale Meldungen und endet wegen fehlender SEC-Kontaktangabe mit Exitcode 2. Der Fehlerstatus verhindert einen falschen Vollständigkeitsnachweis.

## Implementiert und synthetisch geprüft, noch nicht produktiv bewiesen

- Eigene Test-ID `signal1.0-execution60-v1`, eigener Zustands-/Journalpfad; 10.000 EUR aktiv und separate 10.000 EUR Benchmark.
- Start ausschließlich durch die erste erfolgreich gespeicherte prospektive Transaktion. Ende exklusiv 60 lokale Kalendertage später (Europe/Berlin), ohne Rückdatierung, Verlängerung oder automatische Freigabe nach Drawdown.
- Originale v1.0-Signale werden importiert, nicht umgeschrieben. Geänderte Daten-/Ausführungslogik ist separat versioniert. Manifest umfasst Signal-, Engine-, Daten-, Runner-, Journal-, Reporting-, Konfigurations- und Lockdateien. Abweichende Paketversionen werden abgewiesen.
- Benchmark bekommt einen vor dem nächsten Xetra-Open dokumentierten Plan, eine separate Ausführung und deterministisch simulierte Ablehnungen. Wiederholung erfordert einen neuen prospektiven Plan.
- XNYS- und XETR-Kalender statt pauschaler UTC-Zeiten; US-Feiertag und verkürzter Handelstag getestet. Tagesbalken erst 45 Minuten nach jeweiligem Schluss; fehlende Sitzungen werden nicht still aufgefüllt.
- Gegenprüfung aller vier OHLC-Preise, nicht nur Schlusskurs; leere, doppelte, nicht endliche, widersprüchliche oder fehlende abgeschlossene Daten führen zum Fehler. Primär-/Sekundärantworten, URLs, Abrufzeiten, Hashes, Börsenkennung und Session-Schluss werden archiviert.
- FX-Modell: strikt vorangegangener EZB-Referenztag, höchstens sieben Kalendertage alt, plus modellierte FX-Gebühr. Das ist ausdrücklich kein handelbarer Echtzeit-Devisenkurs.
- Ausführungsmodell: nur Long, keine Kredite; bestehende Risiko-/Positionslimits, Gebühren, Spread, Slippage und Ablehnungen. Bekannte Eröffnungskurse gehen unbekannten Intraday-Pfaden vor. Wenn später Stop und Ziel beide berührt werden, wird konservativ Stop zuerst angenommen.
- Unternehmensmaßnahmen: unbestätigte Bedingungen sperren Verarbeitung. Bestätigte Dividende zunächst als nicht verfügbares Guthaben; Zahlung erst mit verifizierter Zahlungsquelle. Split-Anpassung erfordert zusätzliche Bestätigung; Bruchstücke/ungeklärte Maßnahmen sperren. Der Live-Provider liefert diese zusätzlichen Bestätigungen derzeit nicht automatisch.
- Hash-Kette, Dateisperre, isolierte unveränderliche Transaktionsordner und atomarer CURRENT-Zeiger. Frühere Transaktion muss vor Folgeverarbeitung in Git committed sein. Ein Git-Commit oder eine Hash-Kette ist kein unabhängiger manipulationssicherer Zeitstempeldienst.
- Kursbedingter MAE nur als konservative Tagesdaten-Grenze, kein exakter Intraday-Verlust. Währungseffekt abgeschlossener Trades wird separat protokolliert. Rendite netto nach Modellkosten, vor Steuern.
- Neue Berichte kennen keine 55-Handelstage-Mindestlaufzeit oder automatische Verlängerung. Die historischen Altberichte bleiben unangetastet und ihre Jobs gesperrt.

## Echte Läufe und Fehlernachweise

| Lauf | UTC-Zeitraum der HTTP-Erfassung | Ergebnis |
|---|---|---|
| Preflight `20261103T063900-ae69d640d732` | 06:39:00 bis 06:40:57 | Exit 2; EUNL.DE ungültiger abgeschlossener Balken; kein Start |
| Paper-Ausführungsversuch `20261103T070855-c2ff90fc1e94` | 07:08:55 bis 07:10:10 | Exit 2; derselbe Blocker; kein CURRENT, kein Orderjournal und keine Ausführung |
| Research `20261103T070658334547Z` | Abrufstart 07:06:58 | 30 Titel, 2.051 neue Eingänge; Exit 2 wegen fehlendem SEC_USER_AGENT |

EUNL.DE, 2. November 2026, Yahoo-Rohantwort: Open 129,5050048828125; High 130,2949981689453; Low 129,13999938964844; Volume 789.064; **Close null**. Der separate Metadatenwert `regularMarketPrice=129.93` wurde bewusst nicht als endgültiger Tages-Schlusskurs eingesetzt. Zusätzliche Anfragen mit anderem Zeitraum an query1/query2 ergaben HTTP 429. Es wurde kein Schutzkriterium gelockert und kein neuer Handelstag erfunden.

Der Erstabruf des EUNL-Schlusskurses scheitert vor dessen Zweitquellenabruf. Der EUNL-S&P-Global-/StockAnalysis-Parser ist deshalb in diesen Läufen nicht live bewiesen. Yahoo und Nasdaq sind getrennte Abrufwege; die vollständige Unabhängigkeit ihrer vorgelagerten Datenlieferketten ist nicht zertifiziert. Historische Signalbalken werden auf Plausibilität geprüft, jedoch nicht jeder historische Balken unabhängig bestätigt.

## Research und Automatisierung

- Bestehender ChatGPT Research-Desk stündlich aktiv; mehrere tatsächliche Chat-Auswertungen liegen vor. Wochenbericht sonntags aktiv. Beide Prompts verlangen 60 Kalendertage ab belegtem Start, keine automatische Verlängerung und kein Echtgeld. Keine neue doppelte ChatGPT-Aufgabe angelegt.
- Der zusätzliche Python-Intake verwendet das eingefrorene 30-Aktien-Universum, priorisiert offene Positionen und NVDA/AMD/MSFT, dedupliziert Eingänge und verweist auf vorhandene Thesen. Er schreibt ausschließlich in einen neuen Research-Bereich.
- Der Intake bleibt ein regelbasierter Rechercheeingang. Wirtschaftliche Interpretation, Quellengegenprüfung, Gegenargumente und Widerlegungskriterien bleiben Aufgabe des ChatGPT-Desks; Nachrichten sind keine automatischen Handelssignale.
- Der neue Actions-Workflow prüft Tests und echte Daten, sammelt Research, persistiert dessen isolierte Ergebnisse und bewahrt auch Fehlerbelege als Artefakte (90 Tage). Gemeinsame Schreibgruppe `market-check`. **Keine geplante Paper-Ausführung.** Der Workflow ist Bestandteil des Draft-PR und noch nicht als produktiver Standardbranch-Prozess nachgewiesen.
- Historische Claude-Routinen, Warteschlangen und Thesen werden nicht verändert. Der bestehende Monitor bleibt aktiv, einschließlich seines noch ungelösten SEC-Fehlers.

## Verbleibende konkrete Startblocker

1. Vollständiger endgültiger EUNL-Tagesbalken plus funktionierende unabhängige Gegenquelle; danach gesamten Live-Preflight erneut bestehen.
2. Automatisierter, belastbarer Bezug der Bedingungen relevanter Kapitalmaßnahmen einschließlich Dividenden-Zahlungstagen. Bis dahin Sperre bei betroffenen Beständen; keine Behauptung einer vollständigen Corporate-Action-Versorgung.
3. Echte Kontaktangabe als Repository-Variable `SEC_USER_AGENT`. Es wurde keine E-Mail-Adresse erfunden. Ohne sie bleiben SEC-Fundamentaldaten und vollständige Primärquellenüberwachung fehlerhaft.
4. Review/Integration der PRs, erfolgreiche Actions-Ausführung und dauerhafte Veröffentlichung prospektiver Pläne vor der ersten angenommenen Ausführung. Aktuell kein erfolgreicher vollständiger Benchmark-/Aktien-Ausführungszyklus mit echten Daten.
5. Operative 60-Tage-Ausführung erst nach den vorgenannten Nachweisen anschließen; Wochen-/Abschlussberichte und Heartbeat dann mit echten Laufdaten verifizieren. Der Prototyp ersetzt keine bereits validierte Produktionsinfrastruktur.

## Reproduktion und Export

Im Paket: `01-safety.patch` und `02-forward60.patch` in dieser Reihenfolge auf einen sauberen Checkout des geprüften Standardbranch-Bestands anwenden (`git apply --check`, dann `git apply`). Alternativ enthält `berdan-technical-phase.bundle` die lokale Git-Historie samt Implementierungscommit. Rohdaten und Research-Ergebnisse liegen zusätzlich im Evidence-Verzeichnis, mit Manifesten und SHA-256-Prüfsummen; sie sind historische Nachweise, keine neuen Live-Eingaben.

```bash
python -m venv .venv
.venv/bin/pip install -r requirements-pt60.lock
.venv/bin/python -m pytest -q
.venv/bin/python scripts/pt60_run.py --output audit/new-preflight
# Nur bei vollständig bestandenen Voraussetzungen, rein virtuell:
.venv/bin/python scripts/pt60_run.py --execute
```

Der letzte Befehl ist keine Aussage, dass die Voraussetzungen bereits vorliegen. Bei Datenfehlern muss er mit Fehlerstatus enden und darf keinen Teststart erzeugen. Nach 60 Tagen folgt ausschließlich Ergebnisprüfung; jede mögliche Echtgeldphase wäre separat freizugeben. Es gibt keine Brokeranbindung und keine Broker-Schreibrechte.
