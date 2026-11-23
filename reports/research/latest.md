# Research-Monitor – 23.11.2026 22:27 UTC
Regelbasierte Erfassung (Python). Analysen durch Claude stehen in `research/analyses/`.
Quellen: offizielle Newsrooms ✓ · Google News/Yahoo RSS ✓ · SEC EDGAR: inaktiv (Kontaktangabe fehlt)

## Überblick
| Unternehmen | Kurs | Umsatz TTM | Op. Marge | FCF-Marge | Eingepreistes Wachstum | Neue Ereignisse (hoch/mittel/niedrig) |
|---|---|---|---|---|---|---|
| [NVDA](../../research/db/companies/NVDA.md) | 165.05 USD | – | – | – | – | 0/1/16 |
| [AMD](../../research/db/companies/AMD.md) | 453.46 USD | – | – | – | – | 0/0/18 |
| [MSFT](../../research/db/companies/MSFT.md) | 492.50 USD | – | – | – | – | 0/0/18 |

## Neue wichtige Ereignisse
- **mittel** NVDA 2026-11-23: [Kursbewegung +31.5 % am 2026-11-23](https://finance.yahoo.com/quote/NVDA) – Marktdaten, inoffiziell, ohne Zweitquelle; Regel: Tagesbewegung ≥ 8 %

## Zur KI-Analyse vorgemerkt: 0

## Nachrichtenabruf (Google News RSS, Yahoo Finance RSS)
- NVDA: 14 abgerufen, 14 neu, 0 Dubletten verworfen
- AMD: 18 abgerufen, 18 neu, 0 Dubletten verworfen
- MSFT: 19 abgerufen, 18 neu, 0 Dubletten verworfen

## Datenfehler (dieser Lauf)
- `sec:alle|kontakt_fehlt`: SEC verlangt einen User-Agent mit echter Kontaktadresse: Repository-Variable SEC_USER_AGENT setzen (z. B. 'Vorname Nachname name@domain.de'). (seit 74 Läufen)
- `news_google:NVDA`: HTTPError: 503 Server Error: Service Unavailable for url: https://news.google.com/rss/search?q=NVIDIA+OR+NVDA+stock+when:2d&hl=en-US&gl=US&ceid=US:en (seit 1 Läufen)
- `news_google:AMD`: HTTPError: 503 Server Error: Service Unavailable for url: https://news.google.com/rss/search?q=%22Advanced+Micro+Devices%22+OR+%22AMD+stock%22+OR+%22AMD+shares%22+when:2d&hl=en-US&gl=US&ceid=US:en (seit 1 Läufen)
- `news_google:MSFT`: HTTPError: 503 Server Error: Service Unavailable for url: https://news.google.com/rss/search?q=Microsoft+stock+OR+MSFT+OR+%22Microsoft+earnings%22+OR+Azure+when:2d&hl=en-US&gl=US&ceid=US:en (seit 1 Läufen)
