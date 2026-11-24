# Research-Monitor – 24.11.2026 22:31 UTC
Regelbasierte Erfassung (Python). Analysen durch Claude stehen in `research/analyses/`.
Quellen: offizielle Newsrooms ✓ · Google News/Yahoo RSS ✓ · SEC EDGAR: inaktiv (Kontaktangabe fehlt)

## Überblick
| Unternehmen | Kurs | Umsatz TTM | Op. Marge | FCF-Marge | Eingepreistes Wachstum | Neue Ereignisse (hoch/mittel/niedrig) |
|---|---|---|---|---|---|---|
| [NVDA](../../research/db/companies/NVDA.md) | 155.38 USD | – | – | – | – | 0/1/63 |
| [AMD](../../research/db/companies/AMD.md) | 413.27 USD | – | – | – | – | 0/1/41 |
| [MSFT](../../research/db/companies/MSFT.md) | 496.13 USD | – | – | – | – | 0/0/42 |

## Neue wichtige Ereignisse
- **mittel** NVDA 2026-11-24: [Nvidia CFO’s Quick Stint as CEO; State Street Focuses on New Initiatives](https://news.google.com/rss/articles/CBMisAFBVV95cUxPekw0ODMxem9Id1ZpTGpxNEc3akczZkFMa09hM2RzSDZpcEJLNzZEUmwxTlVvZWNIdElGQVJhZm15MDd2eXBtRGdWQlRQdXFFRDJEYUdrUVdIMDJBamxLQmR1ZklYbzBsYWxsVWF3aUdPR2FrQWFJLV95SGtGLTVQd2doSnk0MlAxTkpIVko4N1JLMGRzcEp1cDNQeFppc0piZ2xDcG1qVzh4eG9RcTRwdw?oc=5) – Sekundärquelle, Stufe A (etabliertes Wirtschaftsmedium); Regel: Schlüsselwörter ['ceo', 'cfo'] in etabliertem Medium
- **mittel** AMD 2026-11-24: [Kursbewegung -8.9 % am 2026-11-24](https://finance.yahoo.com/quote/AMD) – Marktdaten, inoffiziell, ohne Zweitquelle; Regel: Tagesbewegung ≥ 8 %

## Zur KI-Analyse vorgemerkt: 0

## Nachrichtenabruf (Google News RSS, Yahoo Finance RSS)
- NVDA: 115 abgerufen, 64 neu, 14 Dubletten verworfen
- AMD: 120 abgerufen, 41 neu, 19 Dubletten verworfen
- MSFT: 119 abgerufen, 42 neu, 20 Dubletten verworfen

## Datenfehler (dieser Lauf)
- `sec:alle|kontakt_fehlt`: SEC verlangt einen User-Agent mit echter Kontaktadresse: Repository-Variable SEC_USER_AGENT setzen (z. B. 'Vorname Nachname name@domain.de'). (seit 77 Läufen)
