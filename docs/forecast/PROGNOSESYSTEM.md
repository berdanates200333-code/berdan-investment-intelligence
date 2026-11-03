# Prognosesystem FC1-1.0: ChatGPT gegen Claude, 60 Tage (virtuell)

Start 03.11.2026, Ende 02.01.2027 (60 Kalendertage), danach Gesamtauswertung. Keine Echtgeldorders; Regeln eingefroren (Änderung = neue Regelversion, prospektiv).

## Struktur (getrennte Journale je KI)
| Datei | Inhalt |
|---|---|
| `forecast/<ki>/prognosen.jsonl` | Prognosejournal, append-only, Hash-Kette, Prognose-ID je Eintrag |
| `forecast/<ki>/bewertungen.jsonl` | automatische Erfolgskontrolle je Prognose und Horizont (1/5/20 Handelstage) |
| `forecast/<ki>/handel.jsonl` | virtuelle Trades (10.000 € je KI), getrennt von Prognosen |
| `forecast/ops_status.json` | Datenstatus der letzten Kontrolle |
`<ki>` = `claude` oder `chatgpt`. Die ersten Claude-Prognosen sind per SHA-256 in `tests/test_forecast.py` festgeschrieben.

## Regeln
- Journalpflicht vor Bewertungszeitraum: `jr.add` lehnt Prognosen ab, sobald das 1-Tages-Ziel (14:30 UTC am Zieltag = US-Eröffnung) erreicht ist. Keine Überschreibung (doppelte ID → Fehler); Korrektur = neue Prognose.
- Zielkurse werden aus Referenzkurs × Prozentprognose berechnet. Pflichtfelder: Instrument-ID, Referenzkurs/Währung/Datum/Quelle, Entscheidung, 3 Horizonte (Prozent, Zieltermin, P(positiv)), Gründe, Gegenargumente, Falsifikation, Quellen, Belastbarkeit.
- Bewertung: tatsächliche Änderung = Schlusskurs am n-ten Handelstag nach Referenzdatum ÷ Schlusskurs Referenzdatum (Yahoo, Stooq-Gegenprüfung falls erreichbar). Richtung richtig = Vorzeichen stimmt; Wahrscheinlichkeitsfehler = Brier-Score; „Entscheidung sinnvoll“: KAUFEN ⇔ Ergebnis nach 0,3 % Rundreisekosten > 0, NICHT KAUFEN/VERKAUFEN ⇔ Ergebnis ≤ 0,3 %, HALTEN ⇔ > 0. Nicht handelbare Instrumente (z. B. Indizes) werden mit `entscheidung_bewerten=false` nur als Prognose gewertet.
- Datenmangel > 5 Tage nach Fälligkeit → „nicht auswertbar“ (zählt nicht in die Trefferquote, wird separat ausgewiesen). Offene Prognosen verfälschen keine Quote.
- Portfolios: je 10.000 €, kein Hebel, keine Leerverkäufe, ≤ 25 % je Position, Gebühr 1 €/Order, Spread+Slippage 0,10 %/Seite, Währungsumrechnung 0,25 %, Trade nur mit zuvor journalisierter Prognose und verifiziertem Kurs. Benchmark vorab: MSCI World (EUNL.DE) und S&P 500 (SXR8.DE) buy-and-hold ab 03.11.2026.

## Unabhängigkeit der KIs — ehrliche Grenzen
Alle Dateien liegen im selben Repo, technisch lesbar. Verabredet: Claude liest `forecast/chatgpt/` und Vergleichsberichte nie vor Abgabe der eigenen Tagesprognose; ChatGPT liest `forecast/claude/` nicht (Nutzer gibt ChatGPT nur Kursdaten, nicht die Claude-Ergebnisse). Das ist organisatorisch, nicht technisch erzwungen. Die automatische Erfolgskontrolle liest nur Kursdaten und Zielwerte.

## ChatGPT-Anbindung
ChatGPT kann nicht selbst ins Repo schreiben. Weg: ChatGPT erzeugt die Tagesprognosen als JSON-Liste im Schema unten → Nutzer startet in GitHub Actions „ChatGPT-Prognosen ins Journal übernehmen“ und fügt die JSON ein (vor US-Eröffnung, 14:30 UTC). Zeitstempel = Eingang im Journal/Commit; der behauptete ChatGPT-Zeitpunkt zählt nicht. **Fairnessrisiko:** ChatGPT hat ohne Webzugriff keine verifizierten Kurse – Referenzkurse muss der Nutzer aus derselben Quelle bereitstellen (`forecast/ops_status.json` oder Yahoo), damit beide dieselbe Datenbasis haben.

Schema je Prognose (alle Felder Pflicht): `prognose_id` (z. B. `CHATGPT-2026-11-04-NVDA-001`), `instrument` {`id`,`name`,`yahoo`}, `referenz` {`kurs`,`waehrung`,`datum`,`quelle`}, `horizonte` {`"1"`,`"5"`,`"20"`: {`tage`,`zieltermin`,`erwartung_pct`,`p_positiv`}}, `entscheidung` (KAUFEN|HALTEN|VERKAUFEN|NICHT KAUFEN), `gruende`, `gegenargumente`, `falsifikation`, `quellen`, `belastbarkeit` (belastbar|eingeschraenkt|nicht_belastbar), optional `trade_zulaessig`, `positionsgroesse`.

## Automatisierung: Status
Siehe Abschnitt im Chat-Bericht; maßgeblich ist `forecast/ops_status.json` nach dem ersten Lauf von „Prognose-Erfolgskontrolle“.
