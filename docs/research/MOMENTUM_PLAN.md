# Vorab-Registrierung: Momentum-Forschung M1–M3

Festgelegt am 31.10.2026, **bevor** die Daten geladen oder angesehen wurden. Dieser Plan wird nicht nachträglich geändert.
Abweichungen werden im Ergebnisbericht ausdrücklich als solche benannt. FT1 bleibt davon unberührt.

## Frage
Bringt eine regelbasierte Rotation in die zuletzt stärksten Branchen (Momentum) nach Kosten und Steuern
einen wirtschaftlichen Vorteil gegenüber einem breiten Aktienmarkt, der nur gehalten wird, bei höchstens 5 Minuten Aufwand im Monat?

## Daten
- **Primär:** Kenneth R. French Data Library, *10 Industry Portfolios* (wertgewichtet, Monatsrenditen inkl.
  Dividenden, USA, seit 07/1926) sowie *Fama/French 3 Factors* (Markt und risikofreier Zins RF, 1-Monats-T-Bill).
  Diese Daten sind frei von Survivorship-Bias, denn Branchenportfolios enthalten alle Aktien, die zum jeweiligen Zeitpunkt existierten.
  Die Monatsrenditen beziehen sich auf das Monatsende. Es sind keine Durchschnittskurse.
- **Sekundär (Umsetzbarkeit):** US-Sektor-ETFs (SPDR Select Sector seit 12/1998) über Yahoo, Monatswerte bereinigt.
- Abruf ausschließlich über einen GitHub-Actions-Workflow. Die Dateien werden mit Prüfsumme im Repo gespeichert.

## Strategien (abschließende Liste)
Signal am Monatsende t, nur mit Renditen bis einschließlich t, gehalten im Monat t+1 (lag 1).
- **M1 Relatives Momentum:** Die Branchen werden nach ihrer Rendite über L Monate gerankt. Dabei werden die letzten S Monate übersprungen.
  Die besten N werden gleichgewichtet gehalten, monatliche Neugewichtung.
  Raster: L ∈ {6, 12}, S ∈ {0, 1}, N ∈ {2, 3, 5}, das sind 12 Varianten.
- **M2 Doppeltes Momentum:** wie M1. Eine ausgewählte Branche wird aber nur gehalten, wenn ihre L-Monats-Rendite
  über dem risikofreien Zins desselben Zeitraums liegt. Sonst liegt ihr Anteil in Cash (RF). 12 Varianten.
- **M3 Niedriger Umschlag:** wie M2, aber eine gehaltene Branche wird erst verkauft, wenn sie aus den besten N+2 fällt
  (Puffer gegen häufige Wechsel, weniger Kosten und Steuern). 12 Varianten.

## Vergleichsmaßstäbe
- Gesamtmarkt (Fama/French Mkt = Mkt-RF + RF), nur halten
- Alle 10 Branchen gleichgewichtet, monatlich neu gewichtet (prüft, ob der Effekt nur aus der Gleichgewichtung kommt)
- Cash (RF)

## Annahmen
- Kosten 0,2 % je Seite auf das umgeschichtete Volumen; Sensitivität mit 0,5 %
- Sensitivität mit lag 2 (ein Monat zusätzliche Verzögerung)
- Steuer-Szenario: 26,375 %, Teilfreistellung 30 % (Aktien-ETF), Verlustvortrag, Liquidation am Ende

## Auswahl und Prüfung
1. **In-Sample 1927–1969:** Die beste Variante nach Sharpe Ratio (Überschussrendite über RF) wird gewählt, je Familie und insgesamt.
2. **Out-of-Sample 1970–heute:** Die gewählte Variante wird geprüft. Zusätzlich werden **alle 36 Varianten** berichtet, damit die Streuung sichtbar ist.
3. **Walk-Forward:** Ab 1940 wird alle 10 Jahre die beste Variante nur auf Basis der Vergangenheit gewählt und für die nächsten 10 Jahre angewandt.
4. Datenmüll-Kontrolle: Es werden genau 36 Varianten getestet. Weitere Varianten werden im Bericht als „nachträglich“ gekennzeichnet.

## Erfolgskriterium (vorab festgelegt)
„Historisch vielversprechend“ gilt nur, wenn **alle** Punkte erfüllt sind:
1. Out-of-Sample: Die gewählte Variante schlägt den Gesamtmarkt nach Kosten bei der Rendite p.a. **oder** hat eine höhere Sharpe Ratio
   bei höchstens gleich großem maximalem Verlust.
2. Walk-Forward: Die Mehrrendite gegenüber dem Markt ist in mindestens 60 % der Jahrzehnte positiv.
3. Bei lag 2 und 0,5 % Kosten bleibt mindestens die Hälfte des Vorsprungs erhalten.
4. Nach Steuern (Szenario) bleibt ein positiver Vorsprung gegenüber dem Markt, der nur gehalten wird.

Ist ein Punkt nicht erfüllt, wird Momentum **nicht** in einen Forward-Test übernommen, oder nur mit ausdrücklicher Begründung.

## Bekannte Risiken
Industry Momentum ist seit 1999 veröffentlicht (Moskowitz/Grinblatt), und der Effekt kann seitdem schwächer geworden sein.
Momentum ist anfällig für abrupte Einbrüche („Momentum Crashes“, z. B. 2009). Branchenportfolios lassen sich nicht direkt kaufen,
Sektor-ETFs haben eigene Kosten und Abweichungen vom Index.
