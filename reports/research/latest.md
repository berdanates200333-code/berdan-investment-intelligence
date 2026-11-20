# Research-Monitor – 20.11.2026 06:19 UTC
Regelbasierte Erfassung (Python). Analysen durch Claude stehen in `research/analyses/`.
Quellen: offizielle Newsrooms ✓ · Google News/Yahoo RSS ✓ · SEC EDGAR: inaktiv (Kontaktangabe fehlt)

## Überblick
| Unternehmen | Kurs | Umsatz TTM | Op. Marge | FCF-Marge | Eingepreistes Wachstum | Neue Ereignisse (hoch/mittel/niedrig) |
|---|---|---|---|---|---|---|
| [NVDA](../../research/db/companies/NVDA.md) | 145.98 USD | – | – | – | – | 0/1/47 |
| [AMD](../../research/db/companies/AMD.md) | 489.19 USD | – | – | – | – | 0/0/20 |
| [MSFT](../../research/db/companies/MSFT.md) | 498.30 USD | – | – | – | – | 0/0/14 |

## Neue wichtige Ereignisse
- **mittel** NVDA 2026-11-20: [California Attorney General Issues Investigative Subpoena to Nvidia](https://news.google.com/rss/articles/CBMiowFBVV95cUxPU1JnZlB6YVZ4SGVkcGZoWFc3eWVGdjY2T3g2ZXhoZ2NrcXd5NjZNTUx0ZE9wZ2I0Uk9fNGxyal9pWnZYdS0wa0tKYUlpem5PSllfSWFueWw3VnY5aVM1andIeTZadW1ZSEduazNsWTNXemlITUpDV0R1d3N1WU9aNG9JSk1kSklNTlBHTXlCb2ttZ3otUW95Zld4YWlQS3pNbjdn?oc=5) – Sekundärquelle, Stufe A (etabliertes Wirtschaftsmedium); Regel: Schlüsselwörter ['subpoena'] in etabliertem Medium

## Zur KI-Analyse vorgemerkt: 0

## Nachrichtenabruf (Google News RSS, Yahoo Finance RSS)
- NVDA: 117 abgerufen, 48 neu, 12 Dubletten verworfen
- AMD: 114 abgerufen, 20 neu, 27 Dubletten verworfen
- MSFT: 117 abgerufen, 14 neu, 22 Dubletten verworfen

## Datenfehler (dieser Lauf)
- `sec:alle|kontakt_fehlt`: SEC verlangt einen User-Agent mit echter Kontaktadresse: Repository-Variable SEC_USER_AGENT setzen (z. B. 'Vorname Nachname name@domain.de'). (seit 63 Läufen)
