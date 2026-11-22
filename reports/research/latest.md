# Research-Monitor – 22.11.2026 06:10 UTC
Regelbasierte Erfassung (Python). Analysen durch Claude stehen in `research/analyses/`.
Quellen: offizielle Newsrooms ✓ · Google News/Yahoo RSS ✓ · SEC EDGAR: inaktiv (Kontaktangabe fehlt)

## Überblick
| Unternehmen | Kurs | Umsatz TTM | Op. Marge | FCF-Marge | Eingepreistes Wachstum | Neue Ereignisse (hoch/mittel/niedrig) |
|---|---|---|---|---|---|---|
| [NVDA](../../research/db/companies/NVDA.md) | 125.53 USD | – | – | – | – | 0/1/26 |
| [AMD](../../research/db/companies/AMD.md) | 424.39 USD | – | – | – | – | 0/0/7 |
| [MSFT](../../research/db/companies/MSFT.md) | 484.52 USD | – | – | – | – | 0/0/16 |

## Neue wichtige Ereignisse
- **mittel** NVDA 2026-11-21: [The Danger of Jensen Huang’s Handshake Deals at Nvidia](https://news.google.com/rss/articles/CBMicEFVX3lxTE1fdkZ5R1J5S3R5UjEzbTdiVW1OTl9RRkFkcFdyYTJNVHpOMVR0TTlQM0YxUUI3VFZwdVEzSFdKMmdCTDVla3VBY3dtOGVxTnEwWFdyeFJneFEwTkZTb3FQQkZveUdGNUI2allxaUNZcVI?oc=5) – Sekundärquelle, Stufe A (etabliertes Wirtschaftsmedium); Regel: Schlüsselwörter ['deal'] in etabliertem Medium

## Zur KI-Analyse vorgemerkt: 0

## Nachrichtenabruf (Google News RSS, Yahoo Finance RSS)
- NVDA: 119 abgerufen, 27 neu, 54 Dubletten verworfen
- AMD: 94 abgerufen, 7 neu, 15 Dubletten verworfen
- MSFT: 119 abgerufen, 16 neu, 34 Dubletten verworfen

## Datenfehler (dieser Lauf)
- `sec:alle|kontakt_fehlt`: SEC verlangt einen User-Agent mit echter Kontaktadresse: Repository-Variable SEC_USER_AGENT setzen (z. B. 'Vorname Nachname name@domain.de'). (seit 69 Läufen)
