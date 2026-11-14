# Research-Monitor – 14.11.2026 13:07 UTC
Regelbasierte Erfassung (Python). Analysen durch Claude stehen in `research/analyses/`.
Quellen: offizielle Newsrooms ✓ · Google News/Yahoo RSS ✓ · SEC EDGAR: inaktiv (Kontaktangabe fehlt)

## Überblick
| Unternehmen | Kurs | Umsatz TTM | Op. Marge | FCF-Marge | Eingepreistes Wachstum | Neue Ereignisse (hoch/mittel/niedrig) |
|---|---|---|---|---|---|---|
| [NVDA](../../research/db/companies/NVDA.md) | 162.85 USD | – | – | – | – | 0/1/36 |
| [AMD](../../research/db/companies/AMD.md) | 534.06 USD | – | – | – | – | 0/0/7 |
| [MSFT](../../research/db/companies/MSFT.md) | 523.88 USD | – | – | – | – | 0/1/7 |

## Neue wichtige Ereignisse
- **mittel** NVDA 2026-11-14: [Nvidia exposed to possible lawsuits after Jensen Huang’s downfall](https://news.google.com/rss/articles/CBMihAFBVV95cUxObGtpTHJsZ0pHR0VpRUx2NlRFcVNnZ1ZvazVNR2tSR2dwcHUtb1MtLWVCTURERFl2QWR1RjNNWXZnVDZBeldsaVNHTzRuTzRZMjNibVdMSkJrclNTT1BucGFlX2RjWjVkTW8wWkJZSjhFTnZKX0QxVXdicl9IaDRGai1uVGw?oc=5) – Sekundärquelle, Stufe A (etabliertes Wirtschaftsmedium); Regel: Schlüsselwörter ['lawsuit'] in etabliertem Medium
- **mittel** MSFT 2026-11-12: [Microsoft apologizes for massive outage that took down Outlook and other 365 services](https://news.google.com/rss/articles/CBMifEFVX3lxTE8zWVd0VTRLTkFhaHlDLTNmZUNmLXkzd3ZLQVBULVd3Wk5GTDBPNzA1TkRGSmlzM0NlTURMX01hdmZHSHE2SW1zbE5OTE80ZjhfX1BZMTFJY2pyUGJjYktrVEJzT0VGelQxQmE5RjhlZkxEcjUwQ21KWnRTZS0?oc=5) – Sekundärquelle, Stufe A (etabliertes Wirtschaftsmedium); Regel: Schlüsselwörter ['outlook'] in etabliertem Medium

## Zur KI-Analyse vorgemerkt: 0

## Nachrichtenabruf (Google News RSS, Yahoo Finance RSS)
- NVDA: 119 abgerufen, 37 neu, 20 Dubletten verworfen
- AMD: 117 abgerufen, 7 neu, 18 Dubletten verworfen
- MSFT: 113 abgerufen, 8 neu, 18 Dubletten verworfen

## Datenfehler (dieser Lauf)
- `sec:alle|kontakt_fehlt`: SEC verlangt einen User-Agent mit echter Kontaktadresse: Repository-Variable SEC_USER_AGENT setzen (z. B. 'Vorname Nachname name@domain.de'). (seit 46 Läufen)
