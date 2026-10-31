# Regelwerk FT1 – Version 1.1 (Betriebs- und Datenregeln)

Gültig ab: 31.10.2026, Journal-Eintrag `typ: regelaenderung` (Version 1.1).
Vorgängerversion: [`REGELWERK_FT1.md`](REGELWERK_FT1.md) (v1.0, unverändert archiviert).
Änderungshistorie: [`REGELWERK_AENDERUNGEN.md`](REGELWERK_AENDERUNGEN.md)

## Was gleich bleibt (Strategie, unverändert gegenüber v1.0)
- Portfolios BENCH (100 % MSCI World, nur halten) und TREND (70 % MSCI World, 20 % Xetra-Gold, 10 % Bitcoin)
- 12-Monats-Trendfilter je Tranche; Cash 0 %
- Ausführung zum ersten Tagesschlusskurs **nach dem Datum** der Signalerstellung
- Kosten 0,2 % (ETF/ETC) bzw. 0,5 % (Krypto) je Seite, 10.000 € virtuell je Portfolio
- Alle bis zum 31.10.2026 protokollierten Signale (Journal-Einträge 1–4) bleiben unverändert gültig.
  Ihre offenen Orders werden nach den Ausführungsregeln von v1.1 abgewickelt.

## Was v1.1 präzisiert
### 1. Monatsabschluss
- Ein Monat gilt als abgeschlossen, sobald in **Europe/Berlin** der Folgemonat begonnen hat.
- **Xetra-Instrumente (MSCI World, Xetra-Gold):** Der Monatsschluss ist der Schlusskurs des letzten
  Xetra-Handelstags des Monats. Das sind Werktage ohne die ganztägigen Schließtage
  1.1., Karfreitag, Ostermontag, 1.5., 24.12., 25.12., 26.12. und 31.12.
  Beispiel Oktober 2026: Fr 30.10. (der 31.10. ist ein Samstag).
- **Bitcoin:** Der Tagesbalken ist der UTC-Kalendertag, gehandelt wird täglich. Der Monatsschluss ist der
  Schlusskurs des letzten Kalendertags. Beispiel Oktober 2026: Sa 31.10., abgeschlossen am 1.11. um 00:00 UTC.
- Fehlt der Kurs des erwarteten letzten Handelstags, wird **kein Signal** erzeugt. Das Signal
  wird beim nächsten Lauf erneut versucht und im Bericht als „aufgeschoben“ geführt.

### 2. Datenprüfung (Voraussetzung für Signale und Ausführungen)
- Ein Kurs gilt nur dann als geprüft, wenn eine Zweitquelle **am selben Datum** übereinstimmt:
  - unabhängiger Anbieter (z. B. CoinGecko für Bitcoin): Abweichung höchstens 1,5 %
  - gleiche ISIN an einem anderen deutschen Handelsplatz (MSCI World): höchstens 2,5 %. Das ist nur eingeschränkt
    unabhängig, weil derselbe Datenanbieter dahintersteht. Es wird im Bericht mit „≈“ gekennzeichnet.
  - unabhängiger Proxy (Xetra-Gold gegen tokenisiertes Gold PAXG bei CoinGecko): Das Kursverhältnis darf höchstens
    2,5 % vom Median der 60 vorherigen gemeinsamen Tage abweichen
- Nur **abgeschlossene** Tagesbalken zählen: der Xetra-Kurs eines Tages erst ab 18:00 Uhr Berlin,
  der Bitcoin-Kurs eines UTC-Tages erst nach dessen Ende.
- Ist der Ausführungskurs fehlend, unvollständig oder nicht bestätigt, wird **nicht ausgeführt**. Die Order
  bleibt offen und wird zum ersten Ausführungskurs ausgeführt, der sich später bestätigen lässt.
  Ein späterer Kurs ersetzt ihn nicht: Maßgeblich bleibt der erste Schlusskurs nach dem Signal.
- Fehlen Daten für eine gehaltene Position, wird sie mit dem letzten bekannten Kurs bewertet und im Bericht markiert.

### 3. Benachrichtigungen (bewusst selten)
1. Neues Signal KAUF/VERKAUF oder virtuelle Ausführung
2. Warnschwelle −10 % vom Höchststand **neu** überschritten
3. Extreme Tagesbewegung: ETF/Gold ab 4 %, Krypto ab 12 %, einmal je Kurstag
4. Datenproblem im 2. Lauf in Folge, danach jeden 5. Lauf
5. Freitags Wochenbericht, zugleich Lebenszeichen des Systems
6. Technischer Fehler (Absturz, fehlgeschlagener Test, Journal verändert): sofort

### 4. Zeitplan
Montag bis Freitag um 18:40 Uhr Europe/Berlin, mit automatischer Sommer- und Winterzeit. Höchstens ein planmäßiger Lauf pro Tag.

## Ausschlüsse (unverändert)
Kein Echtgeld, keine Broker-Verbindung, kein Hebel, keine Leerverkäufe.
