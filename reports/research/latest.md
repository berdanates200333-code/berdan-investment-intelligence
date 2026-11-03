# Research-Monitor – 03.11.2026 06:06 UTC
Regelbasierte Erfassung (Python). Analysen durch Claude stehen in `research/analyses/`.
Quellen: offizielle Newsrooms ✓ · Google News/Yahoo RSS ✓ · SEC EDGAR: inaktiv (Kontaktangabe fehlt)

## Überblick
| Unternehmen | Kurs | Umsatz TTM | Op. Marge | FCF-Marge | Eingepreistes Wachstum | Neue Ereignisse (hoch/mittel/niedrig) |
|---|---|---|---|---|---|---|
| [NVDA](../../research/db/companies/NVDA.md) | 202.06 USD | – | – | – | – | 0/1/30 |
| [AMD](../../research/db/companies/AMD.md) | 466.84 USD | – | – | – | – | 0/0/13 |
| [MSFT](../../research/db/companies/MSFT.md) | 507.12 USD | – | – | – | – | 0/0/19 |

## Neue wichtige Ereignisse
- **mittel** NVDA 2026-11-03: [Nvidia’s Huang Gave Blessing to Marvell-Lumentum Megadeal](https://news.google.com/rss/articles/CBMirAFBVV95cUxNVGc4MkZNbUd3YTNkQkFXYWFOeXYxNzFTeFlJekFzWmFtcjFfbnJLZlR0ODB2RkFiU2p3YVRROU9zSDhQaWpUTlpUdGhXbDZTWk9QYjJHQVFEeS1XUkZ6R01FeEd5V3g4eXhRYmZkeU9EeFNiUkdqZ1hxSGswWXhla2VGQ1lKcEQ2bVQ2VmFYbVdwOEswTEhhSEpxZ1lBQ0pfSXhHOWlPNVN6aDVw?oc=5) – Sekundärquelle, Stufe A (etabliertes Wirtschaftsmedium); Regel: Schlüsselwörter ['deal'] in etabliertem Medium

## Zur KI-Analyse vorgemerkt: 0

## Nachrichtenabruf (Google News RSS, Yahoo Finance RSS)
- NVDA: 118 abgerufen, 31 neu, 11 Dubletten verworfen
- AMD: 91 abgerufen, 13 neu, 12 Dubletten verworfen
- MSFT: 80 abgerufen, 19 neu, 10 Dubletten verworfen

## Datenfehler (dieser Lauf)
- `sec:alle|kontakt_fehlt`: SEC verlangt einen User-Agent mit echter Kontaktadresse: Repository-Variable SEC_USER_AGENT setzen (z. B. 'Vorname Nachname name@domain.de'). (seit 12 Läufen)
