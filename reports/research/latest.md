# Research-Monitor – 19.11.2026 13:33 UTC
Regelbasierte Erfassung (Python). Analysen durch Claude stehen in `research/analyses/`.
Quellen: offizielle Newsrooms ✓ · Google News/Yahoo RSS ✓ · SEC EDGAR: inaktiv (Kontaktangabe fehlt)

## Überblick
| Unternehmen | Kurs | Umsatz TTM | Op. Marge | FCF-Marge | Eingepreistes Wachstum | Neue Ereignisse (hoch/mittel/niedrig) |
|---|---|---|---|---|---|---|
| [NVDA](../../research/db/companies/NVDA.md) | 150.96 USD | – | – | – | – | 0/1/53 |
| [AMD](../../research/db/companies/AMD.md) | 530.14 USD | – | – | – | – | 0/0/30 |
| [MSFT](../../research/db/companies/MSFT.md) | 508.29 USD | – | – | – | – | 0/0/36 |

## Neue wichtige Ereignisse
- **mittel** NVDA 2026-11-18: [Moody’s Lowers Nvidia’s Ratings Outlook to Stable From Positive](https://news.google.com/rss/articles/CBMitAFBVV95cUxOdDduRmdCRExobWhOYnpFNkpNNVo4VE1aZ2I4alRxem5qNXNkcUJwVk1ZNXhSNGRzWmZwX0djSTVFVFktaFFFejhRRGFpaEx5TUF2aEZHZTMyYWRocThJM0s1eElwdXNlSkdZYXpmc1lYYUFValVmcG1nQ1dVck0tbmM1djRtdDR5ejQ2b095dGV6TWpwTzB2aEZXX0VWdUtGc1dyakpubkNhNGZCc2FvdGxUbG4?oc=5) – Sekundärquelle, Stufe A (etabliertes Wirtschaftsmedium); Regel: Schlüsselwörter ['outlook'] in etabliertem Medium

## Zur KI-Analyse vorgemerkt: 0

## Nachrichtenabruf (Google News RSS, Yahoo Finance RSS)
- NVDA: 118 abgerufen, 54 neu, 15 Dubletten verworfen
- AMD: 101 abgerufen, 30 neu, 17 Dubletten verworfen
- MSFT: 118 abgerufen, 36 neu, 15 Dubletten verworfen

## Datenfehler (dieser Lauf)
- `sec:alle|kontakt_fehlt`: SEC verlangt einen User-Agent mit echter Kontaktadresse: Repository-Variable SEC_USER_AGENT setzen (z. B. 'Vorname Nachname name@domain.de'). (seit 61 Läufen)
