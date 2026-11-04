# Research-Monitor – 04.11.2026 13:21 UTC
Regelbasierte Erfassung (Python). Analysen durch Claude stehen in `research/analyses/`.
Quellen: offizielle Newsrooms ✓ · Google News/Yahoo RSS ✓ · SEC EDGAR: inaktiv (Kontaktangabe fehlt)

## Überblick
| Unternehmen | Kurs | Umsatz TTM | Op. Marge | FCF-Marge | Eingepreistes Wachstum | Neue Ereignisse (hoch/mittel/niedrig) |
|---|---|---|---|---|---|---|
| [NVDA](../../research/db/companies/NVDA.md) | 206.69 USD | – | – | – | – | 0/0/57 |
| [AMD](../../research/db/companies/AMD.md) | 483.90 USD | – | – | – | – | 0/1/58 |
| [MSFT](../../research/db/companies/MSFT.md) | 520.99 USD | – | – | – | – | 0/0/41 |

## Neue wichtige Ereignisse
- **mittel** AMD 2026-11-04: [AMD shares jump as AI-driven data-center strength fuels growth outlook](https://news.google.com/rss/articles/CBMisgFBVV95cUxOT1otSGFrSy03TGU4SkFJWHJ0SlJER0pMU0FvV3RIZm1udEtsLTlqazJwbzFEX1lNR3NGYWdNRnRBMDc1ZEk0elNtb2xHcXFFOEFqSnVsWkVRSTBpeHBPUEwtNDZtSUxuZUpKSnM1aXFlX2VUczJlNWRFSXM3MGxmRXAyYkt0dUloMlhaYVJZUVhqNmU2cGVpNkJaMXY3Sm5Qck04ZjNtbHdBSC02Q3hxd3BR?oc=5) – Sekundärquelle, Stufe A (etabliertes Wirtschaftsmedium); Regel: Schlüsselwörter ['outlook'] in etabliertem Medium

## Zur KI-Analyse vorgemerkt: 0

## Nachrichtenabruf (Google News RSS, Yahoo Finance RSS)
- NVDA: 120 abgerufen, 57 neu, 21 Dubletten verworfen
- AMD: 119 abgerufen, 59 neu, 32 Dubletten verworfen
- MSFT: 120 abgerufen, 41 neu, 19 Dubletten verworfen

## Datenfehler (dieser Lauf)
- `sec:alle|kontakt_fehlt`: SEC verlangt einen User-Agent mit echter Kontaktadresse: Repository-Variable SEC_USER_AGENT setzen (z. B. 'Vorname Nachname name@domain.de'). (seit 16 Läufen)
