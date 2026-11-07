# Research-Monitor – 07.11.2026 22:12 UTC
Regelbasierte Erfassung (Python). Analysen durch Claude stehen in `research/analyses/`.
Quellen: offizielle Newsrooms ✓ · Google News/Yahoo RSS ✓ · SEC EDGAR: inaktiv (Kontaktangabe fehlt)

## Überblick
| Unternehmen | Kurs | Umsatz TTM | Op. Marge | FCF-Marge | Eingepreistes Wachstum | Neue Ereignisse (hoch/mittel/niedrig) |
|---|---|---|---|---|---|---|
| [NVDA](../../research/db/companies/NVDA.md) | 186.64 USD | – | – | – | – | 0/1/44 |
| [AMD](../../research/db/companies/AMD.md) | 449.04 USD | – | – | – | – | 0/0/19 |
| [MSFT](../../research/db/companies/MSFT.md) | 530.61 USD | – | – | – | – | 0/0/23 |

## Neue wichtige Ereignisse
- **mittel** NVDA 2026-11-06: [IonQ CEO Doubles Down on Vision for Quantum Dominance After Blowout Earnings](https://news.google.com/rss/articles/CBMidkFVX3lxTE5IOHV3RnpIOVlwUHhxQU1qVWcweG9NaHZxVHBFM1lOdVhrem41UTFOT1NGMjI2VEg2aEdsYWVmaFZkWWUzU2R3blA4VEMtVnlENGUyN1lCYkQwemJtR0lxNlJJRm5VeE90TWFsY21kNGo5c0FQWnc?oc=5) – Sekundärquelle, Stufe A (etabliertes Wirtschaftsmedium); Regel: Schlüsselwörter ['ceo'] in etabliertem Medium

## Zur KI-Analyse vorgemerkt: 0

## Nachrichtenabruf (Google News RSS, Yahoo Finance RSS)
- NVDA: 120 abgerufen, 45 neu, 13 Dubletten verworfen
- AMD: 75 abgerufen, 19 neu, 14 Dubletten verworfen
- MSFT: 76 abgerufen, 23 neu, 7 Dubletten verworfen

## Datenfehler (dieser Lauf)
- `sec:alle|kontakt_fehlt`: SEC verlangt einen User-Agent mit echter Kontaktadresse: Repository-Variable SEC_USER_AGENT setzen (z. B. 'Vorname Nachname name@domain.de'). (seit 26 Läufen)
