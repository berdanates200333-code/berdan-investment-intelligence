# Research-Monitor – 13.11.2026 22:21 UTC
Regelbasierte Erfassung (Python). Analysen durch Claude stehen in `research/analyses/`.
Quellen: offizielle Newsrooms ✓ · Google News/Yahoo RSS ✓ · SEC EDGAR: inaktiv (Kontaktangabe fehlt)

## Überblick
| Unternehmen | Kurs | Umsatz TTM | Op. Marge | FCF-Marge | Eingepreistes Wachstum | Neue Ereignisse (hoch/mittel/niedrig) |
|---|---|---|---|---|---|---|
| [NVDA](../../research/db/companies/NVDA.md) | 162.85 USD | – | – | – | – | 0/2/75 |
| [AMD](../../research/db/companies/AMD.md) | 534.06 USD | – | – | – | – | 0/1/41 |
| [MSFT](../../research/db/companies/MSFT.md) | 523.88 USD | – | – | – | – | 0/0/46 |

## Neue wichtige Ereignisse
- **mittel** NVDA 2026-11-13: [Wall Street Loses a Powerful Dealmaker After Nvidia’s CEO Is Ousted](https://news.google.com/rss/articles/CBMihwFBVV95cUxNbXBvOHJYRmdHTG5FaUpvVVRoRFZaLUlWeXNHQ01ZZi1ReXBJRUVIUnNCN0g5blRzNjdCUE9VNGJPQnI2S29obU9SdmpLTU5mMEhJRDVsQTNKM093b3Z6NzhTTF92NDI1T3lIZmZCQzNHSHo1bHpYbExlM05WR0F0cmduSHpwTnc?oc=5) – Sekundärquelle, Stufe A (etabliertes Wirtschaftsmedium); Regel: Schlüsselwörter ['ceo', 'deal'] in etabliertem Medium
- **mittel** NVDA 2026-11-13: [Arm boss Rene Haas approached in Nvidia CEO search](https://news.google.com/rss/articles/CBMihAFBVV95cUxQV2dGZ3JjRGJZdHNqSWRVak9nOFhBSnZCc1U3R1NVUVB5MmNyWFdvUlduZ1o5VFpzYkxMNmZXYnVFWXFJazQteUNZNGYzN2xXMGtXYU1ELVgwQjc4TUdEbDVfWTJJRVZqajllWS1RUkt6WkR1RDZ4WUlPWjBXTHc4cXZMaVo?oc=5) – Sekundärquelle, Stufe A (etabliertes Wirtschaftsmedium); Regel: Schlüsselwörter ['ceo'] in etabliertem Medium
- **mittel** AMD 2026-11-13: [Kursbewegung -8.8 % am 2026-11-13](https://finance.yahoo.com/quote/AMD) – Marktdaten, inoffiziell, ohne Zweitquelle; Regel: Tagesbewegung ≥ 8 %

## Zur KI-Analyse vorgemerkt: 0

## Nachrichtenabruf (Google News RSS, Yahoo Finance RSS)
- NVDA: 119 abgerufen, 77 neu, 8 Dubletten verworfen
- AMD: 118 abgerufen, 41 neu, 32 Dubletten verworfen
- MSFT: 115 abgerufen, 46 neu, 14 Dubletten verworfen

## Datenfehler (dieser Lauf)
- `sec:alle|kontakt_fehlt`: SEC verlangt einen User-Agent mit echter Kontaktadresse: Repository-Variable SEC_USER_AGENT setzen (z. B. 'Vorname Nachname name@domain.de'). (seit 44 Läufen)
