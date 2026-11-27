# Research-Monitor – 27.11.2026 22:30 UTC
Regelbasierte Erfassung (Python). Analysen durch Claude stehen in `research/analyses/`.
Quellen: offizielle Newsrooms ✓ · Google News/Yahoo RSS ✓ · SEC EDGAR: inaktiv (Kontaktangabe fehlt)

## Überblick
| Unternehmen | Kurs | Umsatz TTM | Op. Marge | FCF-Marge | Eingepreistes Wachstum | Neue Ereignisse (hoch/mittel/niedrig) |
|---|---|---|---|---|---|---|
| [NVDA](../../research/db/companies/NVDA.md) | 150.49 USD | – | – | – | – | 0/1/68 |
| [AMD](../../research/db/companies/AMD.md) | 424.54 USD | – | – | – | – | 0/0/35 |
| [MSFT](../../research/db/companies/MSFT.md) | 492.85 USD | – | – | – | – | 0/0/30 |

## Neue wichtige Ereignisse
- **mittel** NVDA 2026-11-27: [Bankers in Asia Face an AI Financing Hangover](https://news.google.com/rss/articles/CBMivwFBVV95cUxNNXVYUkdPUEhhWHNhWmtoaHZOTndGbWRWeFdGVWpyN3VseDNzSG9DX0NzeHhfV1BsU0pnaHEyQURwZ1hQZnJtQ3Vqc2UzdWRDR2dhNUN4NW5Vdk1tZk93LWFIN3RzMGhONzgzbjhlN2RGbG9IZ2NGMWpYSFRnN0RIaXUyRnA2TmRIOFZiMUUxTTNXT0VzaDZTZFdFY2xxNDBkVW42M2E2MmJxQ1NKSTF3eExVcHZSSmpOTXJsRGphZw?oc=5) – Sekundärquelle, Stufe A (etabliertes Wirtschaftsmedium); Regel: Schlüsselwörter ['ban'] in etabliertem Medium

## Zur KI-Analyse vorgemerkt: 0

## Nachrichtenabruf (Google News RSS, Yahoo Finance RSS)
- NVDA: 119 abgerufen, 69 neu, 26 Dubletten verworfen
- AMD: 100 abgerufen, 35 neu, 18 Dubletten verworfen
- MSFT: 56 abgerufen, 30 neu, 9 Dubletten verworfen

## Datenfehler (dieser Lauf)
- `sec:alle|kontakt_fehlt`: SEC verlangt einen User-Agent mit echter Kontaktadresse: Repository-Variable SEC_USER_AGENT setzen (z. B. 'Vorname Nachname name@domain.de'). (seit 86 Läufen)
