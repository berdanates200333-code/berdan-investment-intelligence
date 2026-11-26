# Research-Monitor – 26.11.2026 22:30 UTC
Regelbasierte Erfassung (Python). Analysen durch Claude stehen in `research/analyses/`.
Quellen: offizielle Newsrooms ✓ · Google News/Yahoo RSS ✓ · SEC EDGAR: inaktiv (Kontaktangabe fehlt)

## Überblick
| Unternehmen | Kurs | Umsatz TTM | Op. Marge | FCF-Marge | Eingepreistes Wachstum | Neue Ereignisse (hoch/mittel/niedrig) |
|---|---|---|---|---|---|---|
| [NVDA](../../research/db/companies/NVDA.md) | 149.30 USD | – | – | – | – | 0/0/52 |
| [AMD](../../research/db/companies/AMD.md) | 406.03 USD | – | – | – | – | 0/0/9 |
| [MSFT](../../research/db/companies/MSFT.md) | 489.93 USD | – | – | – | – | 0/0/33 |

## Neue wichtige Ereignisse
- keine

## Zur KI-Analyse vorgemerkt: 0

## Nachrichtenabruf (Google News RSS, Yahoo Finance RSS)
- NVDA: 118 abgerufen, 51 neu, 16 Dubletten verworfen
- AMD: 20 abgerufen, 9 neu, 2 Dubletten verworfen
- MSFT: 96 abgerufen, 33 neu, 17 Dubletten verworfen

## Datenfehler (dieser Lauf)
- `sec:alle|kontakt_fehlt`: SEC verlangt einen User-Agent mit echter Kontaktadresse: Repository-Variable SEC_USER_AGENT setzen (z. B. 'Vorname Nachname name@domain.de'). (seit 83 Läufen)
- `news_google:AMD`: HTTPError: 429 Client Error: Too Many Requests for url: https://news.google.com/rss/search?q=%22Advanced+Micro+Devices%22+OR+%22AMD+stock%22+OR+%22AMD+shares%22+when:2d&hl=en-US&gl=US&ceid=US:en (seit 1 Läufen)
