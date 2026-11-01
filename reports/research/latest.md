# Research-Monitor – 01.11.2026 05:56 UTC
Regelbasierte Erfassung (Python). Analysen durch Claude stehen in `research/analyses/`.
Quellen: offizielle Newsrooms ✓ · Google News/Yahoo RSS ✓ · SEC EDGAR: inaktiv (Kontaktangabe fehlt)

## Überblick
| Unternehmen | Kurs | Umsatz TTM | Op. Marge | FCF-Marge | Eingepreistes Wachstum | Neue Ereignisse (hoch/mittel/niedrig) |
|---|---|---|---|---|---|---|
| [NVDA](../../research/db/companies/NVDA.md) | 204.64 USD | – | – | – | – | 0/1/30 |
| [AMD](../../research/db/companies/AMD.md) | 504.80 USD | – | – | – | – | 0/0/8 |
| [MSFT](../../research/db/companies/MSFT.md) | 521.91 USD | – | – | – | – | 0/0/26 |

## Neue wichtige Ereignisse
- **mittel** NVDA 2026-10-30: [Nvidia stock surges as revenue beats forecasts](https://news.google.com/rss/articles/CBMiZ0FVX3lxTFB4a053cWxZVkhBLTdTVkw5ODRnT3BiZ2NLRkc5SHNoMVRsdXhJMTN2VmVWdmthSloxQUpTODZibF9oejBQc2NPcTZzMG1LeTJZVF9qM2xnRy03d01iQnEweEFwVGstMkE?oc=5) – Sekundärquelle, Stufe A (etabliertes Wirtschaftsmedium); Regel: Schlüsselwörter ['forecast'] in etabliertem Medium

## Zur KI-Analyse vorgemerkt: 0

## Nachrichtenabruf (Google News RSS, Yahoo Finance RSS)
- NVDA: 120 abgerufen, 31 neu, 39 Dubletten verworfen
- AMD: 99 abgerufen, 8 neu, 18 Dubletten verworfen
- MSFT: 119 abgerufen, 26 neu, 15 Dubletten verworfen

## Datenfehler (dieser Lauf)
- `sec:alle|kontakt_fehlt`: SEC verlangt einen User-Agent mit echter Kontaktadresse: Repository-Variable SEC_USER_AGENT setzen (z. B. 'Vorname Nachname name@domain.de'). (seit 6 Läufen)
