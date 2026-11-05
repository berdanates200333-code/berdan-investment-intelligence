# Research-Monitor – 05.11.2026 22:24 UTC
Regelbasierte Erfassung (Python). Analysen durch Claude stehen in `research/analyses/`.
Quellen: offizielle Newsrooms ✓ · Google News/Yahoo RSS ✓ · SEC EDGAR: inaktiv (Kontaktangabe fehlt)

## Überblick
| Unternehmen | Kurs | Umsatz TTM | Op. Marge | FCF-Marge | Eingepreistes Wachstum | Neue Ereignisse (hoch/mittel/niedrig) |
|---|---|---|---|---|---|---|
| [NVDA](../../research/db/companies/NVDA.md) | 181.60 USD | – | – | – | – | 0/1/85 |
| [AMD](../../research/db/companies/AMD.md) | 404.40 USD | – | – | – | – | 0/1/28 |
| [MSFT](../../research/db/companies/MSFT.md) | 535.93 USD | – | – | – | – | 0/0/40 |

## Neue wichtige Ereignisse
- **mittel** NVDA 2026-11-05: [Kursbewegung -9.3 % am 2026-11-05](https://finance.yahoo.com/quote/NVDA) – Marktdaten, inoffiziell, ohne Zweitquelle; Regel: Tagesbewegung ≥ 8 %
- **mittel** AMD 2026-11-05: [Kursbewegung -17.3 % am 2026-11-05](https://finance.yahoo.com/quote/AMD) – Marktdaten, inoffiziell, ohne Zweitquelle; Regel: Tagesbewegung ≥ 8 %

## Zur KI-Analyse vorgemerkt: 0

## Nachrichtenabruf (Google News RSS, Yahoo Finance RSS)
- NVDA: 120 abgerufen, 81 neu, 23 Dubletten verworfen
- AMD: 114 abgerufen, 28 neu, 40 Dubletten verworfen
- MSFT: 106 abgerufen, 40 neu, 11 Dubletten verworfen

## Datenfehler (dieser Lauf)
- `sec:alle|kontakt_fehlt`: SEC verlangt einen User-Agent mit echter Kontaktadresse: Repository-Variable SEC_USER_AGENT setzen (z. B. 'Vorname Nachname name@domain.de'). (seit 20 Läufen)
