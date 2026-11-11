# Research-Monitor – 11.11.2026 06:13 UTC
Regelbasierte Erfassung (Python). Analysen durch Claude stehen in `research/analyses/`.
Quellen: offizielle Newsrooms ✓ · Google News/Yahoo RSS ✓ · SEC EDGAR: inaktiv (Kontaktangabe fehlt)

## Überblick
| Unternehmen | Kurs | Umsatz TTM | Op. Marge | FCF-Marge | Eingepreistes Wachstum | Neue Ereignisse (hoch/mittel/niedrig) |
|---|---|---|---|---|---|---|
| [NVDA](../../research/db/companies/NVDA.md) | 168.89 USD | – | – | – | – | 0/1/49 |
| [AMD](../../research/db/companies/AMD.md) | 515.21 USD | – | – | – | – | 0/0/11 |
| [MSFT](../../research/db/companies/MSFT.md) | 533.16 USD | – | – | – | – | 0/0/24 |

## Neue wichtige Ereignisse
- **mittel** NVDA 2026-11-10: [US lawmakers push China chip rules after Nvidia CEO allegations](https://news.google.com/rss/articles/CBMiqgFBVV95cUxPQWxqUnFpSkZaOE5LVFZnaWZJaHhteVV2dkdiQnRnX1Zua2Jnd0N3VVBxSzBtOWhETm92Mk9EY0JMbEZMNV9ibThnaWhjd1Y5RTZfMEoxYkk0TTF4Zlk4cmd2RnV2bV85VExSZmswbEJFNmZuZGNBMHYwUklvTjNmdDR1cEIteDdzSlJDc2ZVT3FrS0lZaUVJb1J2MDBvdWtNR0l5NllodU1WUQ?oc=5) – Sekundärquelle, Stufe A (etabliertes Wirtschaftsmedium); Regel: Schlüsselwörter ['ceo'] in etabliertem Medium

## Zur KI-Analyse vorgemerkt: 0

## Nachrichtenabruf (Google News RSS, Yahoo Finance RSS)
- NVDA: 116 abgerufen, 49 neu, 13 Dubletten verworfen
- AMD: 115 abgerufen, 11 neu, 21 Dubletten verworfen
- MSFT: 113 abgerufen, 24 neu, 14 Dubletten verworfen

## Datenfehler (dieser Lauf)
- `sec:alle|kontakt_fehlt`: SEC verlangt einen User-Agent mit echter Kontaktadresse: Repository-Variable SEC_USER_AGENT setzen (z. B. 'Vorname Nachname name@domain.de'). (seit 36 Läufen)
