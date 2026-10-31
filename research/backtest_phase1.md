# Backtest Phase 1 – Trendfilter vs. Buy & Hold (S&P 500, Monatsdaten)

Erstellt: 2026-10-31T11:11:49+00:00 · reproduzierbar mit `python scripts/run_backtest.py`

**Status nach Projektdefinition:** technisch funktionierend, *historisch getestet*. Nicht prospektiv bewährt.

## Annahmen
- Kosten: 0.2 % je Kauf/Verkauf (Gebühr + Spread + Slippage).
- Cash-Verzinsung: 0 % (konservativ; Sensitivität mit 3 % unten).
- Daten: Shiller S&P 500 (Monats**durchschnitte**), Dividenden ab 2023-07 fortgeschrieben, USD, ohne Währungseffekt EUR.
- lag 1 = Signal aus Monat t, gehandelt ab t+1 (optimistisch wegen Durchschnittskursen); lag 2 = konservativ.
- *Sharpe hier ohne Abzug eines risikofreien Zinses (Cash = 0 %).

## In-Sample-Kalibrierung 1881–1969 → beste SMA-Länge (lag 2): **12 Monate**

## Out-of-Sample 1970–heute (nicht zur Kalibrierung genutzt)
| Strategie | CAGR | Vola | Sharpe* | Max DD | Schlechteste 12M | Unterwasser (M) | Wechsel/J | Trefferquote | Profit F. |
|---|---|---|---|---|---|---|---|---|---|
| Buy & Hold S&P 500 (TR) | 11.1 % | 12.6 % | 0.90 | -49.0 % | -40.9 % | 73 | 0.00 | – | – |
| SMA12 Trendfilter (lag 1) | 10.5 % | 9.1 % | 1.15 | -19.2 % | -14.9 % | 36 | 0.97 | 78.6 % | 50.19 |
| SMA10 Standard (lag 1) | 10.2 % | 9.0 % | 1.13 | -19.2 % | -16.9 % | 36 | 1.21 | 71.4 % | 27.33 |
| 12M-Momentum (lag 1) | 10.1 % | 9.7 % | 1.04 | -28.1 % | -26.3 % | 66 | 0.58 | 70.6 % | 51.58 |
| SMA12 Trendfilter (lag 2) | 9.1 % | 9.2 % | 0.99 | -27.1 % | -25.3 % | 39 | 0.97 | 89.3 % | 57.43 |
| SMA10 Standard (lag 2) | 8.6 % | 9.3 % | 0.94 | -26.9 % | -26.9 % | 38 | 1.21 | 82.9 % | 18.06 |
| 12M-Momentum (lag 2) | 9.5 % | 9.7 % | 0.99 | -26.0 % | -23.2 % | 43 | 0.58 | 88.2 % | 53.95 |

## In-Sample 1881–1969 (zum Vergleich)
| Strategie | CAGR | Vola | Sharpe* | Max DD | Schlechteste 12M | Unterwasser (M) | Wechsel/J | Trefferquote | Profit F. |
|---|---|---|---|---|---|---|---|---|---|
| Buy & Hold S&P 500 (TR) | 8.3 % | 15.1 % | 0.60 | -81.7 % | -62.2 % | 182 | 0.00 | – | – |
| SMA12 Trendfilter (lag 1) | 7.9 % | 10.2 % | 0.80 | -50.1 % | -34.1 % | 87 | 1.25 | 61.4 % | 15.32 |
| SMA10 Standard (lag 1) | 8.2 % | 10.0 % | 0.84 | -47.2 % | -38.3 % | 73 | 1.40 | 59.8 % | 14.38 |
| 12M-Momentum (lag 1) | 7.6 % | 10.6 % | 0.75 | -38.3 % | -38.3 % | 92 | 0.93 | 67.2 % | 22.72 |
| SMA12 Trendfilter (lag 2) | 6.5 % | 9.5 % | 0.72 | -40.1 % | -31.2 % | 138 | 1.25 | 67.5 % | 13.42 |
| SMA10 Standard (lag 2) | 6.3 % | 9.6 % | 0.69 | -52.2 % | -38.4 % | 140 | 1.40 | 67.0 % | 9.30 |
| 12M-Momentum (lag 2) | 5.8 % | 10.5 % | 0.59 | -49.9 % | -38.4 % | 102 | 0.93 | 67.2 % | 15.39 |

## Walk-Forward (SMA-Länge jeweils nur aus Vergangenheit gewählt, lag 2)
| Fenster | gewählte SMA |
|---|---|
| 1930-1939 | 14 |
| 1940-1949 | 14 |
| 1950-1959 | 14 |
| 1960-1969 | 13 |
| 1970-1979 | 13 |
| 1980-1989 | 12 |
| 1990-1999 | 12 |
| 2000-2009 | 12 |
| 2010-2019 | 12 |
| 2020-2026 | 12 |

Walk-Forward Strategie: CAGR 8.1 %, Max DD -40.0 %, Vola 9.5 %  
Buy & Hold gleicher Zeitraum: CAGR 10.1 %, Max DD -78.0 %, Vola 15.1 %

## Steuer-Szenario 1970–heute, 10.000 Startkapital (Aktien-ETF, Teilfreistellung 30 %, 26,375 %)
| Strategie | Endwert vor Liq. | lfd. Steuern | Steuer bei Liq. | Endwert netto | CAGR netto |
|---|---|---|---|---|---|
| Buy & Hold S&P 500 (TR) | 2,995,234 | 81,240 | 469,909 | 2,525,325 | 10.2 % |
| SMA12 Trendfilter (lag 2) | 749,159 | 107,064 | 23,444 | 725,715 | 7.8 % |
| 12M-Momentum (lag 2) | 984,208 | 98,804 | 76,233 | 907,975 | 8.3 % |

## Aktien + Gold 1972–heute
| Strategie | CAGR | Vola | Sharpe* | Max DD | Schlechteste 12M | Unterwasser (M) | Wechsel/J | Trefferquote | Profit F. |
|---|---|---|---|---|---|---|---|---|---|
| 100 % Aktien | 11.2 % | 12.5 % | 0.92 | -49.0 % | -40.9 % | 73 | 0.00 | – | – |
| 80/20 Aktien/Gold (monatl. Rebal.) | 11.1 % | 10.6 % | 1.05 | -38.4 % | -34.3 % | 58 | 0.00 | 100.0 % | inf |
| Trend-Tranchen 80/20 (SMA10, lag 2) | 9.0 % | 8.0 % | 1.12 | -22.5 % | -22.5 % | 38 | 2.38 | 69.0 % | 13.85 |

## Sensitivität: SMA12 lag 2 mit 3 % Cash-Zins (OOS)
CAGR 10.0 %, Max DD -25.2 %
