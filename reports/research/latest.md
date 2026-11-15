# Research-Monitor – 15.11.2026 06:03 UTC
Regelbasierte Erfassung (Python). Analysen durch Claude stehen in `research/analyses/`.
Quellen: offizielle Newsrooms ✓ · Google News/Yahoo RSS ✓ · SEC EDGAR: inaktiv (Kontaktangabe fehlt)

## Überblick
| Unternehmen | Kurs | Umsatz TTM | Op. Marge | FCF-Marge | Eingepreistes Wachstum | Neue Ereignisse (hoch/mittel/niedrig) |
|---|---|---|---|---|---|---|
| [NVDA](../../research/db/companies/NVDA.md) | 162.85 USD | – | – | – | – | 0/0/32 |
| [AMD](../../research/db/companies/AMD.md) | 534.06 USD | – | – | – | – | 0/0/4 |
| [MSFT](../../research/db/companies/MSFT.md) | 523.88 USD | – | – | – | – | 0/1/4 |

## Neue wichtige Ereignisse
- **mittel** MSFT 2026-11-13: [Cerebras Stock: Earnings Beat and New Microsoft Partnership](https://news.google.com/rss/articles/CBMie0FVX3lxTE5GV3pHZXI5bHdjSjFjc2JBMEF0UGNGZTBYVUgzZzZ6Smd0dGhTdUdyYzd2QzVYbnBrUkRweWhSWW9OQ1ZWVWotWXlBbHFob05kWUtqSmVwOEhZXzh6azBFZ0haOTh3eXYzazZ3SFluUDRWRW5FYi1EY0FtOA?oc=5) – Sekundärquelle, Stufe A (etabliertes Wirtschaftsmedium); Regel: Schlüsselwörter ['partnership'] in etabliertem Medium

## Zur KI-Analyse vorgemerkt: 0

## Nachrichtenabruf (Google News RSS, Yahoo Finance RSS)
- NVDA: 117 abgerufen, 32 neu, 13 Dubletten verworfen
- AMD: 80 abgerufen, 4 neu, 17 Dubletten verworfen
- MSFT: 115 abgerufen, 5 neu, 26 Dubletten verworfen

## Datenfehler (dieser Lauf)
- `sec:alle|kontakt_fehlt`: SEC verlangt einen User-Agent mit echter Kontaktadresse: Repository-Variable SEC_USER_AGENT setzen (z. B. 'Vorname Nachname name@domain.de'). (seit 48 Läufen)
