# Prognosesystem FC1-1.0 (Stand nach Audit): ChatGPT gegen Claude, 60 Kalendertage, virtuell

**Status: Wettbewerb NICHT gestartet.** Die vier Prognosen vom 03.11.2026 sind unveränderte **Pilotprognosen**. Der Start erfolgt erst, wenn `scripts/fc_gate.py` alle Bedingungen bestätigt (`forecast/wettbewerb_gate.json`) und dann explizit `--start` ausgeführt wird. Kein Rückdatieren, kein Echtgeld.

## Bausteine
| Baustein | Datei |
|---|---|
| Journale je KI (append-only, Hash-Kette) | `forecast/<ki>/prognosen.jsonl`, `bewertungen.jsonl`; Kontojournal `forecast/<ki>/konto/handel.jsonl` |
| Börsenkalender (XNYS/XETR/Krypto 24/7; Sommerzeit, Feiertage, verkürzte Tage) | `bii/forecast/calendars.py` (exchange_calendars); keine feste Eröffnungszeit |
| Datenqualitätsstufen A/B/C | `bii/forecast/quality.py`; Wettbewerb/Ausführung nur Stufe A, Pilot Stufe B |
| Live-Daten mit Zweitquelle | `bii/forecast/live.py` (Yahoo; Nasdaq/Stooq), Rohantworten per SHA-256 protokolliert |
| Gemeinsame Handels-Engine | `bii/papertrading/engine.py` (ein Code für beide KIs); Adapter `bii/forecast/ai_portfolio.py` |
| Blinder Eingang (Commit-Reveal, Serverzeit) | `bii/forecast/commitreveal.py`, `scripts/fc_ingest.py`, Workflow `forecast-intake.yml` |
| Universum (stufenweise) | `forecast/universum.json`, Status `forecast/universum_status.json` |
| Startschranke | `bii/forecast/gate.py`, `scripts/fc_gate.py` |

## Datenqualität (hartes Tor)
A = gültige Balken + Identität/Währung/Handelsplatz + aktuell + unabhängige Zweitquelle bestätigt (O/H/L/C ≤ 2 %). B = gültig, nur eine Quelle. C = ungültig (OHLC inkonsistent, nichtendlich, fehlende Handelstage laut Kalender, veraltet, Sprung > 40 %, falsche Währung/Börse) oder Zweitquelle weicht ab. Unter Mindeststufe wird **nicht bewertet und nicht ausgeführt**; nach 5 Tagen Karenz „nicht auswertbar“ mit Gründen (separat ausgewiesen, nicht in Treffer-/Fehlerquoten). Kursreihen sind split-bereinigt, ohne Dividenden (Preisrendite); Splits im Zeitraum werden markiert.

## Gemeinsame Simulation
Beide KIs: identischer Code, identische Parameter (`rules_v1_0.PARAMS`: Gebühr 1 €, Spread+Slippage 0,10 %/Seite, Währung 0,25 % mit EZB-Vortageskurs, Risiko ≤ 1 % je Trade inkl. Kosten ab Limit, ≤ 5 Positionen, ≤ 20 % je Position, kein Hebel, Drawdown-Pause 10 %). Die KI liefert Prognose-ID, Limit, Stop, Ziel; die Stückzahl bestimmt die gemeinsame Risikoregel. Order wird vor der Ausführung im Kontojournal dokumentiert; Ausführung frühestens in der nächsten Sitzung, nur wenn die Dokumentation vor der Kalender-Eröffnung lag.
**Integration mit PR #10:** `forward60` (Entwurf, anderer Zweig) nutzt dieselbe Engine und `verified_data` mit Nasdaq/StockAnalysis-Zweitquellen sowie fail-closed-Kapitalmaßnahmen; er ist signalgetrieben und eingefroren (Manifest-Hash) und nimmt keine KI-Orders an. Dieser Zweig übernimmt ihn nicht, sondern nutzt die gemeinsame Engine direkt. Beim Merge von PR #10 ist der Datenanbieter `EngineProvider` durch `VerifiedProvider` zu ersetzen (gleiche Schnittstelle: `ohlcv`, `fx`, `crosscheck`, `news`); `engine.py` wurde hier kalenderbasiert geändert (Hash im PR-#10-Manifest neu festschreiben, bevor dessen Start erfolgt).

## Fairness und Blindheit (technisch)
Gleicher Informationsstichtag: `jr.add` verlangt Referenzdatum = letzter abgeschlossener Handelstag laut Kalender; Zieltermine werden gegen den Kalender geprüft. Gleiche Daten/Kosten/Universum: gemeinsamer Datenpfad und Engine. **Commit-Reveal:** erst Hash (bis Eröffnung − 60 min), Klartext erst danach; Zeitstempel = Serverzeit des Eingangsdienstes; Fristverstöße, Hash-Abweichung und fehlender Commit werden abgelehnt. Damit kann keine KI ihre Prognose nach Kenntnis der anderen ändern. **Grenze:** Klartexte vergangener Sitzungen liegen im gemeinsamen Repo; Lesen früherer Prognosen der anderen KI ist nicht technisch verhinderbar (Härtung: privates Eingangs-Repo mit getrennten Deploy-Keys je KI) und die Zuordnung „welche KI hat gepusht“ beruht auf dem Pfad, nicht auf Authentifizierung.

## ChatGPT-Anbindung (Stand: NICHT bewiesen)
Eingang: Push von `forecast/inbox/chatgpt/<sitzung>/{commit,reveal}.json` auf `chatgpt/inbox` (oder die Standardbranch). Der Dienst läuft per Push-Ereignis, ohne manuelle Eingabe. Offen und nicht aus dieser Umgebung prüfbar: ob eine geplante ChatGPT-Aufgabe mit der vorhandenen GitHub-Verbindung im Hintergrund schreiben kann. Bekannt/vermutet: Connector-Zugriffe sind lesend oder bedürfen interaktiver Bestätigung; im Repo erscheinen `codex/*`-Zweige, also kann ein ChatGPT-Agent (Codex) Zweige pushen. Alternative autorisierte Übergabe: Codex-/Agent-Aufgabe, die täglich per Push auf `chatgpt/inbox` schreibt (Zweig per Ruleset auf diesen Akteur beschränkt). **Als funktionsfähig gilt der Weg erst nach 2 unbeaufsichtigten Sitzungen** (Belege `forecast/receipts/chatgpt/*` mit Ereignis `push`; Bedingung `automatik_chatgpt` der Startschranke).

## Bewertung (Prognose ≠ Trading)
Originalwerte bleiben unverändert im Journal. Je Prognose und Horizont (1/5/20 Handelstage laut Kalender): Ist-Änderung, Abweichung (PP), Richtung, Brier, Datenstufen, Vergleichsmodelle **Nullveränderung** und **historische Basisrate** (nur Daten vor dem Referenzdatum), kritische Fehlererklärung. Berichte: Abdeckung (Prognosetage), Bias, Ø absoluter Fehler, Brier gegen Basisrate, nicht auswertbar/offen getrennt. **Tradingperformance** (Nettorendite nach Kosten, Drawdown, Kosten) kommt ausschließlich aus dem Kontozustand der Engine und wird separat berichtet.

## Universum
Stufe 1 (handelbar, USD/US-Sitzungen): 30 Aktien + SPY, QQQ, IWM, GLD; Zulassung nur mit Datenstufe A und Ø-Dollarvolumen ≥ 100 Mio. $ (tägliche Prüfung). Stufe 2 (nur Daten, nicht handelbar): BTC-USD, ETH-USD (Engine unterstützt 24/7 nicht), 4GLD.DE (EUR/Xetra). Benchmark: EUNL.DE (Datenstufe wird geprüft; PR #10 meldete für den 02.11. einen Null-Schlusskurs). ISINs sind aus Wissen eingetragen und als ungeprüft markiert.

## Startschranke
Start nur wenn: ≥ 20 Instrumente + Benchmark zugelassen; für beide KIs ein Probelauf mit echter Ausführung auf Stufe-A-Daten über die gemeinsame Engine; beide KIs ≥ 2 unbeaufsichtigte Commit+Reveal-Sitzungen; Konten unberührt (10.000 €). Start frühestens zur nächsten Sitzung, 60 Kalendertage.
