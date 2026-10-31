# Momentum M1–M3: historische Prüfung (Branchenrotation)

Erstellt 2026-10-31T11:42:49+00:00 · Plan: [`docs/research/MOMENTUM_PLAN.md`](../docs/research/MOMENTUM_PLAN.md) (vor Datenabruf festgelegt) · 36 Varianten · reproduzierbar: `python scripts/run_momentum.py`

**Status:** historisch getestet. Nicht prospektiv bewährt. Kein Einfluss auf FT1.

Daten: Kenneth R. French, 10 Industry Portfolios + F/F-Faktoren (1926-07-01 bis 2026-09-01), Monatsend-Renditen inkl. Dividenden, USD. Kosten 0,2 % je Seite, Cash = T-Bill.

## Ergebnis nach den vorab festgelegten Kriterien
1. Out-of-Sample-Vorteil gegenüber dem Markt: **erfüllt**
2. Walk-Forward: Mehrrendite in mindestens 60 % der Jahrzehnte: **nicht erfüllt** (55.6 %)
3. Robust bei lag 2 und 0,5 % Kosten: **nicht erfüllt**
4. Nach Steuern vor dem Markt: **nicht erfüllt**
→ **Historisch vielversprechend: NEIN**

## In-Sample 1927–1969: beste Variante = **M2 L12 S0 N5**
Beste je Familie: M1: M1 L12 S0 N3, M2: M2 L12 S0 N5, M3: M3 L12 S0 N2

## Out-of-Sample 1970–heute
| Strategie | CAGR | Vola | Sharpe (vs. RF) | Max DD | Schlechteste 12M | Wechsel/J | Kosten p.a. |
|---|---|---|---|---|---|---|---|
| Markt (nur halten) | 11.1 % | 15.8 % | 0.48 | -50.3 % | -42.6 % | 0.0 | 0.0 % |
| 10 Branchen gleichgewichtet | 11.5 % | 15.0 % | 0.52 | -48.1 % | -41.0 % | 0.0 | 0.0 % |
| M1 L12 S0 N3 (IS-beste M1) | 13.0 % | 16.3 % | 0.57 | -43.6 % | -38.6 % | 6.4 | 0.9 % |
| M2 L12 S0 N5 (IS-beste M2) | 11.9 % | 12.9 % | 0.61 | -32.1 % | -27.9 % | 7.2 | 0.8 % |
| M3 L12 S0 N2 (IS-beste M3) | 12.5 % | 16.1 % | 0.55 | -39.4 % | -30.4 % | 2.9 | 0.6 % |

Anteil aller 36 Varianten mit höherer Rendite p.a. als der Markt (OOS): 63.9 %; mit höherer Sharpe Ratio: 72.2 %

## Sensitivität (IS-beste Variante, OOS)
| Annahme | CAGR | Mehrrendite vs. Markt | Sharpe | Max DD |
|---|---|---|---|---|
| Basis (lag 1, 0,2 %) | 11.9 % | 0.8 % | 0.61 | -32.1 % |
| lag 2 | 10.9 % | -0.2 % | 0.52 | -32.1 % |
| Kosten 0,5 % | 10.7 % | -0.5 % | 0.52 | -32.9 % |
| lag 2 + 0,5 % | 9.7 % | -1.4 % | 0.44 | -33.1 % |

## Walk-Forward (Auswahl nur aus Vergangenheitsdaten)
| Fenster | gewählt |
|---|---|
| 1940–1949 | M2 L12 S0 N5 |
| 1950–1959 | M2 L12 S0 N5 |
| 1960–1969 | M2 L12 S0 N5 |
| 1970–1979 | M2 L12 S0 N5 |
| 1980–1989 | M2 L12 S0 N5 |
| 1990–1999 | M2 L12 S0 N5 |
| 2000–2009 | M2 L12 S0 N5 |
| 2010–2019 | M2 L12 S0 N5 |
| 2020–2026 | M2 L12 S0 N5 |

| Jahrzehnt | Strategie p.a. | Markt p.a. | Mehrrendite |
|---|---|---|---|
| 1940er | 9.1 % | 9.5 % | -0.4 % |
| 1950er | 21.4 % | 18.3 % | 3.1 % |
| 1960er | 8.8 % | 8.3 % | 0.5 % |
| 1970er | 9.7 % | 6.1 % | 3.6 % |
| 1980er | 14.7 % | 16.9 % | -2.2 % |
| 1990er | 20.3 % | 18.0 % | 2.3 % |
| 2000er | 4.4 % | -0.4 % | 4.7 % |
| 2010er | 11.4 % | 13.6 % | -2.2 % |
| 2020er | 11.7 % | 15.0 % | -3.2 % |

Gesamt Walk-Forward: Strategie 12.3 % p.a., Max DD -32.1 %; Markt 11.4 % p.a., Max DD -50.3 %

## Steuer-Szenario 1970–heute (10.000 € Start, 26,375 %, Teilfreistellung 30 %)
| | Endwert vor Liquidation | lfd. Steuern | Steuer bei Liquidation | Endwert netto | CAGR netto |
|---|---|---|---|---|---|
| M2 L12 S0 N5 | 2,560,287 | 417,100 | 55,175 | 2,505,112 | 10.2 % |
| Markt (nur halten) | 3,956,061 | 0 | 728,541 | 3,227,519 | 10.7 % |

## Umsetzbarkeit mit US-Sektor-ETFs (2000-02-01–2026-09-01, Regel M2 L12 S0 N5)
Strategie: CAGR 7.8 %, Max DD -22.0 %, Sharpe 0.55, 7.1 Wechsel/J  
SPY: CAGR 8.5 %, Max DD -50.8 %, Sharpe 0.49  
_kurzer Zeitraum, nur Plausibilitätsprüfung; Sektor-ETFs in USD_

## Alle 36 Varianten (OOS 1970–heute, sortiert nach Rendite p.a.)
| Variante | CAGR | Sharpe | Max DD | Wechsel/J |
|---|---|---|---|---|
| M1 L12 S1 N2 | 13.5 % | 0.55 | -48.2 % | 5.4 |
| M1 L12 S0 N3 | 13.0 % | 0.57 | -43.6 % | 6.4 |
| M1 L12 S0 N2 | 12.9 % | 0.53 | -47.5 % | 5.4 |
| M1 L12 S0 N5 | 12.8 % | 0.59 | -40.9 % | 6.9 |
| M2 L12 S0 N3 | 12.8 % | 0.60 | -33.7 % | 6.3 |
| M2 L12 S0 N2 | 12.7 % | 0.54 | -37.1 % | 5.4 |
| M1 L12 S1 N3 | 12.7 % | 0.55 | -40.0 % | 6.4 |
| M1 L6 S0 N2 | 12.6 % | 0.52 | -40.9 % | 6.7 |
| M3 L12 S0 N3 | 12.6 % | 0.59 | -33.2 % | 3.8 |
| M3 L12 S0 N2 | 12.5 % | 0.55 | -39.4 % | 2.9 |
| M2 L12 S1 N2 | 12.4 % | 0.52 | -47.6 % | 5.4 |
| M1 L6 S0 N5 | 12.1 % | 0.55 | -45.5 % | 8.6 |
| M1 L12 S1 N5 | 12.1 % | 0.54 | -41.2 % | 6.9 |
| M2 L12 S0 N5 | 11.9 % | 0.61 | -32.1 % | 7.2 |
| M2 L12 S1 N3 | 11.8 % | 0.53 | -36.3 % | 6.3 |
| M2 L6 S0 N2 | 11.7 % | 0.50 | -27.8 % | 6.9 |
| M1 L6 S0 N3 | 11.6 % | 0.49 | -43.2 % | 8.3 |
| M3 L12 S0 N5 | 11.6 % | 0.58 | -31.6 % | 4.6 |
| M3 L12 S1 N2 | 11.5 % | 0.49 | -46.2 % | 2.9 |
| M3 L12 S1 N3 | 11.5 % | 0.51 | -33.7 % | 3.8 |
| M3 L6 S0 N2 | 11.2 % | 0.50 | -27.3 % | 4.6 |
| M3 L12 S1 N5 | 11.2 % | 0.54 | -31.0 % | 4.6 |
| M3 L6 S0 N3 | 11.2 % | 0.54 | -27.1 % | 5.8 |
| M2 L12 S1 N5 | 10.9 % | 0.52 | -32.1 % | 7.2 |
| M1 L6 S1 N5 | 10.7 % | 0.46 | -46.0 % | 8.6 |
| M1 L6 S1 N3 | 10.6 % | 0.44 | -44.2 % | 8.3 |
| M2 L6 S0 N5 | 10.3 % | 0.51 | -25.2 % | 8.9 |
| M3 L6 S1 N3 | 10.3 % | 0.45 | -33.4 % | 5.8 |
| M2 L6 S0 N3 | 10.2 % | 0.46 | -26.9 % | 8.5 |
| M3 L6 S0 N5 | 10.2 % | 0.51 | -24.7 % | 6.4 |
| M3 L6 S1 N2 | 10.0 % | 0.41 | -37.8 % | 4.6 |
| M1 L6 S1 N2 | 10.0 % | 0.38 | -44.2 % | 6.7 |
| M2 L6 S1 N3 | 9.5 % | 0.40 | -34.2 % | 8.5 |
| M2 L6 S1 N2 | 9.3 % | 0.36 | -34.7 % | 6.9 |
| M3 L6 S1 N5 | 9.3 % | 0.42 | -30.7 % | 6.4 |
| M2 L6 S1 N5 | 9.1 % | 0.41 | -30.2 % | 8.9 |
