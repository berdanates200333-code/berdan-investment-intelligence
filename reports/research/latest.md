# Research-Monitor – 21.11.2026 22:16 UTC
Regelbasierte Erfassung (Python). Analysen durch Claude stehen in `research/analyses/`.
Quellen: offizielle Newsrooms ✓ · Google News/Yahoo RSS ✓ · SEC EDGAR: inaktiv (Kontaktangabe fehlt)

## Überblick
| Unternehmen | Kurs | Umsatz TTM | Op. Marge | FCF-Marge | Eingepreistes Wachstum | Neue Ereignisse (hoch/mittel/niedrig) |
|---|---|---|---|---|---|---|
| [NVDA](../../research/db/companies/NVDA.md) | 125.53 USD | – | – | – | – | 0/1/47 |
| [AMD](../../research/db/companies/AMD.md) | 424.39 USD | – | – | – | – | 0/0/31 |
| [MSFT](../../research/db/companies/MSFT.md) | 484.52 USD | – | – | – | – | 0/0/36 |

## Neue wichtige Ereignisse
- **mittel** NVDA 2026-11-21: [Nvidia Said to Face S.E.C. Probe Into Its Accounting Practices](https://news.google.com/rss/articles/CBMiekFVX3lxTE5qSmxMVy1SN0NxMVRKNy1XTmdKbUJ0WVI4VlUwM3RQWnJvNkE0M1pLVVk3bHJZUUtYWUFJdUJjMllKbXhyYzNOR1dDazVJN2ZmaGxENktCS213Q29Vc2paREMxOEZGZkw5QzNHcU5KRjJxdVBjdHM2SlpR?oc=5) – Sekundärquelle, Stufe A (etabliertes Wirtschaftsmedium); Regel: Schlüsselwörter ['probe'] in etabliertem Medium

## Zur KI-Analyse vorgemerkt: 0

## Nachrichtenabruf (Google News RSS, Yahoo Finance RSS)
- NVDA: 120 abgerufen, 48 neu, 15 Dubletten verworfen
- AMD: 101 abgerufen, 31 neu, 18 Dubletten verworfen
- MSFT: 119 abgerufen, 36 neu, 25 Dubletten verworfen

## Datenfehler (dieser Lauf)
- `sec:alle|kontakt_fehlt`: SEC verlangt einen User-Agent mit echter Kontaktadresse: Repository-Variable SEC_USER_AGENT setzen (z. B. 'Vorname Nachname name@domain.de'). (seit 68 Läufen)
