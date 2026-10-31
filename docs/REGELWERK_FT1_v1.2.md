# Regelwerk FT1 – Version 1.2 (Betriebsregeln)

Gültig ab: 31.10.2026, Journal-Eintrag `typ: regelaenderung` (Version 1.2), **vor der ersten virtuellen Ausführung**.
Vorgänger: [v1.1](REGELWERK_FT1_v1.1.md) · [v1.0](REGELWERK_FT1.md) · Historie: [Änderungen](REGELWERK_AENDERUNGEN.md)

**Die Strategie bleibt unverändert:** Portfolios, Gewichte, 12-Monats-Filter, Kosten, „erster Schlusskurs nach dem Signaldatum“.
Die Journal-Einträge 1–5 bleiben unverändert und sind per Test festgeschrieben.

## Änderungen gegenüber v1.1
1. **Prüfstufen statt Ja/Nein.**
   - `bestaetigt`: Ein unabhängiger Anbieter liefert für dasselbe Instrument am selben Datum einen Kurs innerhalb von 1,5 % (Bitcoin: Yahoo/CoinGecko).
   - `plausibel`: Es gibt nur einen anderen Handelsplatz desselben Anbieters (MSCI World: Xetra/Frankfurt bei Yahoo, 2,5 %) **oder** einen
     Proxy-Vergleich (Xetra-Gold gegen PAXG). Ein Proxy ist **kein identischer Zweitkurs**. Er prüft, ob die Kursbewegung zum Vergleichswert passt.
     Das Verhältnis darf höchstens 2,5 % vom 60-Tage-Median abweichen. Das Kursniveau selbst wird damit nicht bestätigt.
   - Ausführungen und Signale sind ab der Stufe `plausibel` zulässig. Die Stufe wird in jedem Journal-Eintrag gespeichert (`pruefstufe`)
     und im Bericht getrennt ausgewiesen („✓ bestätigt“ bzw. „◐ plausibel“). Ohne bestandene Prüfung gibt es keine Ausführung (unverändert).
2. **T+1-Bestätigung für Xetra-Kurse.** Ein Xetra-Schlusskurs zählt erst ab dem Folgetag (Berlin) als endgültig.
   Grund: Um 18:40 Uhr kann ein Datenanbieter noch einen vorläufigen Wert liefern, und der Vergleichshandelsplatz Frankfurt handelt bis 22 Uhr.
   Der **Ausführungskurs bleibt derselbe** (erster Schluss nach dem Signal), er wird nur einen Tag später erkannt. Bitcoin ist unverändert:
   Ein UTC-Tag zählt nach seinem Ende.
3. **Datenfehler je Instrument und Ursache.** Die Ursachen sind `abruf_fehlgeschlagen`, `zweitquelle_fehlt`, `abweichung`, `veraltet`,
   `order_blockiert`, `signal_aufgeschoben` und `bewertung_mit_altkurs`. Jede Kombination hat einen eigenen Zähler für Läufe in Folge.
   Eine Meldung kommt beim 2. Lauf in Folge, danach bei jedem 5. Lauf. Ein Fehler bei Bitcoin setzt also keinen Zähler für den MSCI World fort.
4. **Veraltete Daten** werden als eigene Ursache erkannt: Der letzte endgültige Kurs ist älter als 4 Tage (Xetra) bzw. 2 Tage (Krypto).

## Prüfung auf veraltete Daten und unbeabsichtigte Ausführungen (31.10.2026)
| Risiko | Befund | Maßnahme |
|---|---|---|
| Ausführung zum Kurs vom Signaltag oder davor | Ausgeschlossen: nur Kurse mit Datum **nach** dem Signaldatum | – |
| Vorläufiger Tageskurs wird als Ausführungskurs genutzt | **Möglich in v1.1** (Xetra-Kurs ab 18:00 Uhr) | v1.2: T+1-Bestätigung |
| Proxy-Prüfung wird als Kursbestätigung missverstanden | In v1.1 als „✓ Proxy“ angezeigt | v1.2: Stufe `plausibel`, eigene Kennzeichnung |
| Veralteter Kurs (Datenfeed steht) löst Ausführung aus | Nicht möglich: ohne neuen Kurs nach dem Signal keine Ausführung. Bisher nur schwach im Bericht sichtbar | v1.2: Ursache `veraltet` mit Zähler und Meldung |
| Fehler bei einem Instrument überdeckt Fehler bei einem anderen | v1.1 hatte einen gemeinsamen Zähler | v1.2: Zähler je Instrument/Ursache |
| Manueller Start des Workflows führt Orders aus | Gleiche Regeln wie beim planmäßigen Lauf; keine Sonderwege | dokumentiert, keine Änderung nötig |
| Tests verändern das echte Journal | Tests nutzen isolierte Testordner (`tmp_path`) | – |
| Nachträgliche Datenkorrektur beim Anbieter | Der Ausführungskurs wird beim Ausführen im Journal festgeschrieben | – |
| Spätere Erkennung nach Ausfall | Ausführung zum korrekten ersten Kurs nach dem Signal; Verzögerung steht im Journal (`erkannt_tage_nach_kurs`) | v1.2: Feld ergänzt |
