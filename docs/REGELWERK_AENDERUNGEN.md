# Änderungshistorie der Forward-Test-Regelwerke

Regeln: Bestehende Journal-Einträge werden nie geändert (Hash-Kette + festgeschriebene Prüfsummen
in `tests/test_journal_pins.py`). Jede Regeländerung wird als eigenes Dokument versioniert und
im Journal mit der SHA-256-Prüfsumme des Dokuments eingetragen.

| Version | Datum | Art | Inhalt | Wirkung auf bisherige Signale |
|---|---|---|---|---|
| FT1 v1.0 | 31.10.2026 | Erstfassung | Portfolios, 12M-Trendfilter, Kosten, Ausführung am ersten Schluss nach Signal | – |
| FT1 v1.1 | 31.10.2026 | Betriebsregeln | Monatsabschluss je Handelskalender (Xetra vs. Bitcoin/UTC), Ausführung und Signale nur mit abgeschlossenen, datumsgenau gegengeprüften Kursen, Benachrichtigungsregeln, Zeitplan | keine. Einträge 1–4 bleiben unverändert. Bis dahin wurde nichts ausgeführt. |
| FT1 v1.2 | 31.10.2026 | Betriebsregeln | Prüfstufen bestätigt/plausibel (Proxy ≠ Zweitkurs), T+1-Bestätigung für Xetra-Kurse, Datenfehler je Instrument und Ursache, Ursache „veraltet“ | keine. Einträge 1–5 bleiben unverändert. Bis dahin wurde nichts ausgeführt. |

## Begründung für die Einstufung als v1.1 statt FT2
v1.0 sah vor, dass Änderungen als neue Version laufen. Die Strategie selbst ändert sich nicht:
Gewichte, Filter, Kosten und Ausführungszeitpunkt sind gleich. v1.1 regelt nur Datenqualität und Ablauf genauer,
und zwar bevor die erste virtuelle Ausführung stattfand. Ein paralleles FT2 mit identischer Strategie
hätte keinen Erkenntniswert. Sollte die Strategie selbst geändert werden, entsteht FT2, und FT1 läuft unverändert weiter.

## Hinweis zu den Signalen vom 31.10.2026
Die ersten Signale beruhen auf dem Monatsschluss **September** 2026. Am Samstag, dem 31.10., war der
Oktober nach Berliner Kalender noch nicht abgeschlossen. Das entspricht v1.0 und bleibt so stehen.
Die Oktober-Signale entstehen beim ersten Lauf ab dem 1.11.2026.
