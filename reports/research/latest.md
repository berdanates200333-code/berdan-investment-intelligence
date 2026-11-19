# Research-Monitor – 19.11.2026 06:15 UTC
Regelbasierte Erfassung (Python). Analysen durch Claude stehen in `research/analyses/`.
Quellen: offizielle Newsrooms ✓ · Google News/Yahoo RSS ✓ · SEC EDGAR: inaktiv (Kontaktangabe fehlt)

## Überblick
| Unternehmen | Kurs | Umsatz TTM | Op. Marge | FCF-Marge | Eingepreistes Wachstum | Neue Ereignisse (hoch/mittel/niedrig) |
|---|---|---|---|---|---|---|
| [NVDA](../../research/db/companies/NVDA.md) | 150.96 USD | – | – | – | – | 0/0/45 |
| [AMD](../../research/db/companies/AMD.md) | 530.14 USD | – | – | – | – | 0/0/16 |
| [MSFT](../../research/db/companies/MSFT.md) | 508.29 USD | – | – | – | – | 0/1/29 |

## Neue wichtige Ereignisse
- **mittel** MSFT 2026-11-18: [US lawmakers seek Microsoft briefing on reported AI deal talks with ByteDance](https://news.google.com/rss/articles/CBMivwFBVV95cUxNdEpRTFc4Q3Nsa085U2xoZldyY1BXSmlhSy0yT00tRzF4eU5QekdiUENlSTQyajA0eU5PVWl0MUpoejlXdXJMVVFPbHRVaGFlZmxoWFA5SHN5VXBpWHJvLUFLMjZISk96bVRuWWs0V3NSblpmWTM3VVZNQ3VHQVNpQTNUOFM5VzdwZ0ZOcHlFX3hmcEJ5ZDhRVXlCS0dCZEwxbXZ3Z09zVjB4N1FGMHo4Qkc4WWEwTG5LdHNWbk14NA?oc=5) – Sekundärquelle, Stufe A (etabliertes Wirtschaftsmedium); Regel: Schlüsselwörter ['deal'] in etabliertem Medium

## Zur KI-Analyse vorgemerkt: 0

## Nachrichtenabruf (Google News RSS, Yahoo Finance RSS)
- NVDA: 119 abgerufen, 45 neu, 11 Dubletten verworfen
- AMD: 89 abgerufen, 16 neu, 11 Dubletten verworfen
- MSFT: 118 abgerufen, 30 neu, 19 Dubletten verworfen

## Datenfehler (dieser Lauf)
- `sec:alle|kontakt_fehlt`: SEC verlangt einen User-Agent mit echter Kontaktadresse: Repository-Variable SEC_USER_AGENT setzen (z. B. 'Vorname Nachname name@domain.de'). (seit 60 Läufen)
