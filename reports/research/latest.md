# Research-Monitor – 06.11.2026 22:16 UTC
Regelbasierte Erfassung (Python). Analysen durch Claude stehen in `research/analyses/`.
Quellen: offizielle Newsrooms ✓ · Google News/Yahoo RSS ✓ · SEC EDGAR: inaktiv (Kontaktangabe fehlt)

## Überblick
| Unternehmen | Kurs | Umsatz TTM | Op. Marge | FCF-Marge | Eingepreistes Wachstum | Neue Ereignisse (hoch/mittel/niedrig) |
|---|---|---|---|---|---|---|
| [NVDA](../../research/db/companies/NVDA.md) | 186.64 USD | – | – | – | – | 0/0/57 |
| [AMD](../../research/db/companies/AMD.md) | 449.04 USD | – | – | – | – | 0/1/37 |
| [MSFT](../../research/db/companies/MSFT.md) | 530.61 USD | – | – | – | – | 0/2/44 |

## Neue wichtige Ereignisse
- **mittel** AMD 2026-11-06: [Kursbewegung +11.0 % am 2026-11-06](https://finance.yahoo.com/quote/AMD) – Marktdaten, inoffiziell, ohne Zweitquelle; Regel: Tagesbewegung ≥ 8 %
- **mittel** MSFT 2026-11-06: [Microsoft is winding down Oracle deal to rent AI cloud capacity, Bloomberg News reports](https://news.google.com/rss/articles/CBMivAFBVV95cUxNN0g4UzRRaV9OckNuUjZYeVcybWl4SnhZUHVRR3pXVTFUdVMtWENOSWRKdjhUQThNTWlRWXd3YVJFTUVaM1hOaFI2UWJ6cDlWZjM4Q3NXTWZDVlJFSTdnS3RqNExHcG93anIxTDhpNXJTRGduSEgxcWNaYnNRYTdOdWF4SzBoZzBLV3o1Wi1ZaEVPWkFXZVJSSWhYZWFSdE9BRFlINGtWWjhhM2FLUEdaYjJQOTBLQ0VCLVIyXw?oc=5) – Sekundärquelle, Stufe A (etabliertes Wirtschaftsmedium); Regel: Schlüsselwörter ['deal'] in etabliertem Medium
- **mittel** MSFT 2026-11-06: [Microsoft Won’t Renew Deal for Renting AI Cloud Capacity From Oracle: Report](https://news.google.com/rss/articles/CBMifkFVX3lxTE9VMldqNUtPTEN1N2JuNFB3OGwwV0k2bnNtbVJObWhoSDRMOUg2ZGh6d0hsUlB4WFF3bDJobDUxNEQ3cEN3dDhBaEl1WUlCRG1mTlNvbkJ6RVNMZ2JNTkhjSVRpckYxRnN0dkVhb3ZBQ1JsM1ZpWFdKNnNQcHdldw?oc=5) – Sekundärquelle, Stufe A (etabliertes Wirtschaftsmedium); Regel: Schlüsselwörter ['deal'] in etabliertem Medium

## Zur KI-Analyse vorgemerkt: 0

## Nachrichtenabruf (Google News RSS, Yahoo Finance RSS)
- NVDA: 118 abgerufen, 56 neu, 15 Dubletten verworfen
- AMD: 99 abgerufen, 37 neu, 26 Dubletten verworfen
- MSFT: 105 abgerufen, 46 neu, 18 Dubletten verworfen

## Datenfehler (dieser Lauf)
- `sec:alle|kontakt_fehlt`: SEC verlangt einen User-Agent mit echter Kontaktadresse: Repository-Variable SEC_USER_AGENT setzen (z. B. 'Vorname Nachname name@domain.de'). (seit 23 Läufen)
