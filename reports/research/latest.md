# Research-Monitor – 25.11.2026 06:13 UTC
Regelbasierte Erfassung (Python). Analysen durch Claude stehen in `research/analyses/`.
Quellen: offizielle Newsrooms ✓ · Google News/Yahoo RSS ✓ · SEC EDGAR: inaktiv (Kontaktangabe fehlt)

## Überblick
| Unternehmen | Kurs | Umsatz TTM | Op. Marge | FCF-Marge | Eingepreistes Wachstum | Neue Ereignisse (hoch/mittel/niedrig) |
|---|---|---|---|---|---|---|
| [NVDA](../../research/db/companies/NVDA.md) | 155.38 USD | – | – | – | – | 0/1/53 |
| [AMD](../../research/db/companies/AMD.md) | 413.27 USD | – | – | – | – | 0/0/10 |
| [MSFT](../../research/db/companies/MSFT.md) | 496.13 USD | – | – | – | – | 0/0/23 |

## Neue wichtige Ereignisse
- **mittel** NVDA 2026-11-24: [Nvidia Option Trader Scores 1,984% Gain After CEO Huang’s Return](https://news.google.com/rss/articles/CBMitAFBVV95cUxNamtGS0VrR2RNa0lSdGhmLXVac3lxSTlBUHJEZWRralBBdkZQRXp0aXlNejZHRG4xZXRqMEJXNHJKUGZ3M2prODN2YjZWVGk4SmI4a3JpNFBWcU5UYUQtUE9YNUd0YVFVZVE3TVRyUUdtVDhSX1UtSDk4OVM1OXZVbVdJMDJoVTU0aWV0TFJzRmYwQlpjcmxCV2FyZTRnalhvcnJlT3ZHSU1ycktHd0gxOHNPRWY?oc=5) – Sekundärquelle, Stufe A (etabliertes Wirtschaftsmedium); Regel: Schlüsselwörter ['ceo'] in etabliertem Medium

## Zur KI-Analyse vorgemerkt: 0

## Nachrichtenabruf (Google News RSS, Yahoo Finance RSS)
- NVDA: 115 abgerufen, 54 neu, 7 Dubletten verworfen
- AMD: 120 abgerufen, 10 neu, 23 Dubletten verworfen
- MSFT: 116 abgerufen, 23 neu, 20 Dubletten verworfen

## Datenfehler (dieser Lauf)
- `sec:alle|kontakt_fehlt`: SEC verlangt einen User-Agent mit echter Kontaktadresse: Repository-Variable SEC_USER_AGENT setzen (z. B. 'Vorname Nachname name@domain.de'). (seit 78 Läufen)
