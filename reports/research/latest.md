# Research-Monitor – 27.11.2026 06:17 UTC
Regelbasierte Erfassung (Python). Analysen durch Claude stehen in `research/analyses/`.
Quellen: offizielle Newsrooms ✓ · Google News/Yahoo RSS ✓ · SEC EDGAR: inaktiv (Kontaktangabe fehlt)

## Überblick
| Unternehmen | Kurs | Umsatz TTM | Op. Marge | FCF-Marge | Eingepreistes Wachstum | Neue Ereignisse (hoch/mittel/niedrig) |
|---|---|---|---|---|---|---|
| [NVDA](../../research/db/companies/NVDA.md) | 149.30 USD | – | – | – | – | 0/0/14 |
| [AMD](../../research/db/companies/AMD.md) | 406.03 USD | – | – | – | – | 0/0/2 |
| [MSFT](../../research/db/companies/MSFT.md) | 489.93 USD | – | – | – | – | 0/0/4 |

## Neue wichtige Ereignisse
- keine

## Zur KI-Analyse vorgemerkt: 0

## Nachrichtenabruf (Google News RSS, Yahoo Finance RSS)
- NVDA: 14 abgerufen, 14 neu, 0 Dubletten verworfen
- AMD: 20 abgerufen, 2 neu, 2 Dubletten verworfen
- MSFT: 19 abgerufen, 4 neu, 1 Dubletten verworfen

## Datenfehler (dieser Lauf)
- `sec:alle|kontakt_fehlt`: SEC verlangt einen User-Agent mit echter Kontaktadresse: Repository-Variable SEC_USER_AGENT setzen (z. B. 'Vorname Nachname name@domain.de'). (seit 84 Läufen)
- `news_google:NVDA`: HTTPError: 503 Server Error: Service Unavailable for url: https://news.google.com/rss/search?q=NVIDIA+OR+NVDA+stock+when:2d&hl=en-US&gl=US&ceid=US:en (seit 1 Läufen)
- `news_google:AMD`: HTTPError: 503 Server Error: Service Unavailable for url: https://news.google.com/rss/search?q=%22Advanced+Micro+Devices%22+OR+%22AMD+stock%22+OR+%22AMD+shares%22+when:2d&hl=en-US&gl=US&ceid=US:en (seit 2 Läufen)
- `news_google:MSFT`: HTTPError: 503 Server Error: Service Unavailable for url: https://news.google.com/rss/search?q=Microsoft+stock+OR+MSFT+OR+%22Microsoft+earnings%22+OR+Azure+when:2d&hl=en-US&gl=US&ceid=US:en (seit 1 Läufen)
