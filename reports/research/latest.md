# Research-Monitor – 17.11.2026 06:15 UTC
Regelbasierte Erfassung (Python). Analysen durch Claude stehen in `research/analyses/`.
Quellen: offizielle Newsrooms ✓ · Google News/Yahoo RSS ✓ · SEC EDGAR: inaktiv (Kontaktangabe fehlt)

## Überblick
| Unternehmen | Kurs | Umsatz TTM | Op. Marge | FCF-Marge | Eingepreistes Wachstum | Neue Ereignisse (hoch/mittel/niedrig) |
|---|---|---|---|---|---|---|
| [NVDA](../../research/db/companies/NVDA.md) | 156.14 USD | – | – | – | – | 0/0/18 |
| [AMD](../../research/db/companies/AMD.md) | 504.28 USD | – | – | – | – | 0/0/11 |
| [MSFT](../../research/db/companies/MSFT.md) | 517.99 USD | – | – | – | – | 0/0/15 |

## Neue wichtige Ereignisse
- keine

## Zur KI-Analyse vorgemerkt: 0

## Nachrichtenabruf (Google News RSS, Yahoo Finance RSS)
- NVDA: 17 abgerufen, 17 neu, 0 Dubletten verworfen
- AMD: 15 abgerufen, 11 neu, 1 Dubletten verworfen
- MSFT: 87 abgerufen, 15 neu, 13 Dubletten verworfen

## Datenfehler (dieser Lauf)
- `sec:alle|kontakt_fehlt`: SEC verlangt einen User-Agent mit echter Kontaktadresse: Repository-Variable SEC_USER_AGENT setzen (z. B. 'Vorname Nachname name@domain.de'). (seit 54 Läufen)
- `news_google:NVDA`: HTTPError: 429 Client Error: Too Many Requests for url: https://news.google.com/rss/search?q=NVIDIA+OR+NVDA+stock+when:2d&hl=en-US&gl=US&ceid=US:en (seit 1 Läufen)
- `news_google:AMD`: HTTPError: 429 Client Error: Too Many Requests for url: https://news.google.com/rss/search?q=%22Advanced+Micro+Devices%22+OR+%22AMD+stock%22+OR+%22AMD+shares%22+when:2d&hl=en-US&gl=US&ceid=US:en (seit 1 Läufen)
