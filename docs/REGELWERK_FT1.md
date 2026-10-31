# Regelwerk FT1 – vorab festgelegt (Forward-Test, virtuell)

Version: FT1 · festgelegt am 31.10.2026, **bevor** ein einziges Live-Signal erzeugt wurde.
Änderungen sind nur als neue Version (FT2 …) zulässig. FT1 läuft dann zum Vergleich unverändert weiter.

## Zweck
Die Frage ist, ob ein einfacher monatlicher Trendfilter in der Praxis dasselbe leistet wie im Backtest: deutlich kleinere Verluste bei etwas geringerer Rendite. Der Maßstab ist ein Welt-ETF, der nur gekauft und gehalten wird.

## Portfolios (je 10.000 € virtuell)
| Portfolio | Zusammensetzung | Regel |
|---|---|---|
| BENCH | 100 % iShares Core MSCI World (IE00B4L5Y983, Xetra, EUR) | Einmal kaufen und halten |
| TREND | 70 % MSCI World · 20 % Xetra-Gold (DE000A0S9GB0) · 10 % Bitcoin (EUR) | Jede Tranche einzeln mit dem 12-Monats-Trendfilter |

## Trendfilter (Regel T1, monatlich)
1. Monatsschluss = letzter verfügbarer Tagesschlusskurs eines abgeschlossenen Kalendermonats.
2. SMA12 = Durchschnitt der letzten 12 Monatsschlüsse (einschließlich des aktuellen).
3. Liegt der Monatsschluss über SMA12, ist die Tranche investiert (Zielgewicht wie oben). Sonst liegt sie in Cash (0 % Zins).
4. Signalerstellung: beim ersten Tageslauf nach Monatsende.
5. Ausführung (virtuell): zum **ersten Tagesschlusskurs nach** dem Zeitpunkt der Signalerstellung. Eine Ausführung zum Signalkurs selbst ist nicht zulässig.
6. Kosten: ETF/ETC 0,2 % je Seite, Bitcoin 0,5 % je Seite.
7. Bei Datenwarnungen (Abweichung zwischen den Quellen über 1,5 % oder unplausibler Kurssprung) wird nicht ausgeführt. Die Order bleibt offen.

## Begründung der Parameter
- SMA12: Im Backtest wurde die Länge nur auf Daten von 1881–1969 gewählt. Der Walk-Forward-Test wählt seit 1980 durchgehend 12. Auf 1970–2026 wurde keine Optimierung vorgenommen.
- Bitcoin ist mit 10 % gedeckelt (Risikoregel des Projekts). **Für die Bitcoin-Tranche gibt es keinen historischen Test**, weil dafür in Phase 1 keine Daten verfügbar waren. Sie wird ausschließlich vorwärts getestet.

## Risikoregeln (Startannahmen)
- Kein Hebel, keine Leerverkäufe, keine Echtgeld-Orders.
- Warnung bei einem Rückgang von 10 % gegenüber dem bisherigen Höchststand des Portfolios.
- Krypto insgesamt höchstens 10 %.

## Erfolgskriterium nach 6 Monaten (vorab festgelegt)
Sechs Monate sind statistisch **nicht** aussagekräftig. Ausgewertet wird trotzdem:
- Wurden alle Signale korrekt, rechtzeitig und ohne nachträgliche Änderung protokolliert? (Prüfung der Technik)
- Rendite und maximaler Rückgang von TREND gegenüber BENCH, nach Kosten.
- Anzahl der Benachrichtigungen und der nötige persönliche Zeitaufwand.
