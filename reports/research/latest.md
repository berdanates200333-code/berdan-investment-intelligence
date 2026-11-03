# Research-Monitor – 03.11.2026 22:19 UTC
Regelbasierte Erfassung (Python). Analysen durch Claude stehen in `research/analyses/`.
Quellen: offizielle Newsrooms ✓ · Google News/Yahoo RSS ✓ · SEC EDGAR: inaktiv (Kontaktangabe fehlt)

## Überblick
| Unternehmen | Kurs | Umsatz TTM | Op. Marge | FCF-Marge | Eingepreistes Wachstum | Neue Ereignisse (hoch/mittel/niedrig) |
|---|---|---|---|---|---|---|
| [NVDA](../../research/db/companies/NVDA.md) | 206.69 USD | – | – | – | – | 0/0/59 |
| [AMD](../../research/db/companies/AMD.md) | 483.90 USD | – | – | – | – | 1/1/57 |
| [MSFT](../../research/db/companies/MSFT.md) | 520.99 USD | – | – | – | – | 0/0/41 |

## Neue wichtige Ereignisse
- **hoch** AMD 2026-11-03: [AMD Reports Third Quarter 2026 Financial Results](https://ir.amd.com/news-events/press-releases/detail/1303/amd-reports-third-quarter-2026-financial-results) – offiziell (Unternehmensmitteilung, Primärquelle); Regel: offizielle Mitteilung zu Geschäftszahlen
- **mittel** AMD 2026-11-03: [AMD Needs a Huge Outlook to Avoid Intel’s Fate as AI Fears Rise](https://news.google.com/rss/articles/CBMitAFBVV95cUxNRW9XeVZ4N0oxZjlNajFBS0ZXT2RDTE02dktLYXJad082NXU5NWctVkQ2aE1iZ01uLWt4WlZXUW51ZUk0ZzRHUWtYd0dGblRReV94empxQlVBMEJjNHBLcExfQWV4aGxIWktWaG04S0tydDdJb1NGSExIN0hGX1hVa04tYlRuQzk3V0kwQ1JSMFRUNkUzRFczU3cwZ1RObTctVUNlUVFrczVpLW9TVTA1NkxGMUI?oc=5) – Sekundärquelle, Stufe A (etabliertes Wirtschaftsmedium); Regel: Schlüsselwörter ['outlook'] in etabliertem Medium

## Zur KI-Analyse vorgemerkt: 1
- `ir:AMD:7351a647da52b9d5`

## Nachrichtenabruf (Google News RSS, Yahoo Finance RSS)
- NVDA: 109 abgerufen, 58 neu, 20 Dubletten verworfen
- AMD: 117 abgerufen, 58 neu, 15 Dubletten verworfen
- MSFT: 119 abgerufen, 41 neu, 26 Dubletten verworfen

## Datenfehler (dieser Lauf)
- `sec:alle|kontakt_fehlt`: SEC verlangt einen User-Agent mit echter Kontaktadresse: Repository-Variable SEC_USER_AGENT setzen (z. B. 'Vorname Nachname name@domain.de'). (seit 14 Läufen)
