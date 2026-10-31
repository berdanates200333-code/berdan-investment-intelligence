# Phase 1 – Bestandsaufnahme, Strategieanalyse, erster Test

Stand: 31.10.2026 · Status: **technisch funktionsfähig, historisch getestet, prospektiv noch nicht bewährt**

---

## A. Technische Bestandsaufnahme (selbst geprüft)

| Funktion | Ergebnis | Nachweis |
|---|---|---|
| Claude Code in der Cloud (diese Sitzung) | ✅ verfügbar: Python, pandas und numpy laufen, Code wird ausgeführt | Diese Sitzung |
| Websuche aus Claude heraus | ✅ verfügbar (Nachrichten, Recherche) | getestet |
| Direkter Abruf von Kursdaten aus der Cloud-Sitzung | ❌ **gesperrt** durch die Netzwerkrichtlinie der Umgebung: Yahoo, Stooq, CoinGecko, Binance, Kraken, EZB, FRED, SEC EDGAR, FMP | Proxy antwortet mit 403 |
| GitHub (Rohdateien, API) | ✅ erreichbar → historische Datensätze von dort geladen | `data/historical/` |
| Finanzdaten-Konnektoren (z. B. Financial Modeling Prep) in Claude | ❌ keine installiert | Konnektor-Liste ist leer |
| Geplante Aufgaben in Claude (Cloud) | ⚠️ Werkzeug in dieser Umgebung vorhanden, aber dieselbe Netzsperre gilt. Laut Anthropic-Hilfe war Cowork mobil zuletzt für Pro als Beta bzw. im Rollout → **nicht verifiziert** | Websuche, Quellen unten |
| GitHub Actions (kostenlose Server mit vollem Internetzugang) | ✅ Workflow ist angelegt, Zeitplan noch **aus** | `.github/workflows/` |

**Folgerung:** Die Zahlenarbeit (Kurse, Signale, Journal) übernimmt am besten **GitHub Actions**. Das ist kostenlos, deterministisch und belastet dein Claude-Kontingent nicht. Claude übernimmt Recherche, Interpretation und Weiterentwicklung.

### Datenquellen (alle kostenlos)
| Zweck | Quelle | Einschränkung |
|---|---|---|
| ETF-/Aktienkurse täglich | Yahoo Finance (inoffiziell) + Stooq als Gegenprüfung | verzögert, inoffizielle Schnittstelle, nur für private Nutzung |
| Krypto | Yahoo (BTC-EUR) + CoinGecko (frei, 365 Tage Historie) | Referenzkurse, kein Börsenplatz |
| Wechselkurse | EZB Data API | täglicher Referenzkurs |
| Unternehmensberichte | SEC EDGAR (frei) | noch nicht angebunden |
| Historie lang | Shiller S&P 500 (1871–2026), Gold monatlich | Monatsdurchschnitte, siehe unten |

Kostenpflichtige Daten (z. B. FMP, EODHD) lohnen sich erst, wenn eine Strategie mit Einzelaktien-Tagesdaten über die Kostenschwelle kommt (siehe Szenarien).

---

## B. Strategievergleich

| Strategie | Ertragspotenzial netto | Aufwand für dich | Automatisierbar | Datenbedarf | Belege | Urteil Phase 1 |
|---|---|---|---|---|---|---|
| **F Regelbasiertes Portfolio (Kern-ETF + Trendfilter)** | Rendite ≈ Markt bis leicht darunter, **Verluste halbiert** | ~5 Min/Monat | voll | gering (Monatsdaten) | über 100 Jahre Daten, Out-of-Sample geprüft | **Test 1 – läuft** |
| B Momentum (ETF-/Sektorrotation, monatlich) | historisch leicht über Markt, schwankend | ~5 Min/Monat | voll | Tageskurse ETFs | breit dokumentierte Anomalie | **Test 2** |
| C/D Swing / Mean Reversion (Rücksetzer im Aufwärtstrend, 3–15 Tage) | potenziell höher, aber kostensensibel | 10–20 Min/Woche | weitgehend | Tagesdaten Einzelaktien ohne Survivorship-Bias | gemischt, oft überoptimiert | **Test 3**, nur mit sauberen Daten |
| A Qualitätsaktien, langfristig | ≈ Markt ± Stockpicking-Risiko | mittel | teilweise (Claude-Recherche) | Fundamentaldaten | gemischt | Beobachtungsliste, kein Signalsystem |
| E Ereignisse (z. B. Kursdrift nach Quartalszahlen) | klein bis mittel, Kosten fressen viel | hoch (enges Timing) | schwer ohne Echtzeit | Gewinnschätzungen (teuer) | dokumentiert, aber schwächer geworden | später |

---

## C. Erster praktischer Test (Backtest, reproduzierbar)

Details: [`research/backtest_phase1.md`](../research/backtest_phase1.md). Aufruf: `python scripts/run_backtest.py`

**Testaufbau:** S&P 500 einschließlich Dividenden, 0,2 % Kosten je Seite, Cash 0 %. Die SMA-Länge wurde nur auf **1881–1969** gewählt. Geprüft wurde auf **1970–2026** (Out-of-Sample), zusätzlich mit einem Walk-Forward-Test.

| Out-of-Sample 1970–2026 | Rendite p.a. | Max. Verlust | Schlechteste 12 Monate |
|---|---|---|---|
| Buy & Hold | **11,1 %** | −49,0 % | −40,9 % |
| SMA12-Trendfilter (konservative Ausführung) | 9,1 % | **−27,1 %** | −25,3 % |
| SMA12, mit 3 % Cash-Zins | 10,0 % | −25,2 % | – |

**Steuern (Szenario, 10.000 € Start, 1970–2026, Aktien-ETF mit 30 % Teilfreistellung):** Buy & Hold endet bei ca. 2,53 Mio. € netto, der Trendfilter bei ca. 0,73 Mio. € netto. Ursache: Jeder Ausstieg realisiert Gewinne und löst Steuern aus. Das senkt den Zinseszins deutlich.

**Ehrliches Fazit:**
1. Der Trendfilter **schlägt den Markt bei der Rendite nicht**. Nach Steuern liegt er klar darunter.
2. Er **halbiert** die großen Verluste (−27 % statt −49 %). Das ist sein einziger, aber realer Vorteil: Er nützt, wenn ein Crash dich sonst zum Verkauf am Tiefpunkt bringen würde oder wenn du Kapital zu einem festen Termin brauchst (Immobilie!).
3. Aktien plus 20 % Gold senkte seit 1972 den maximalen Verlust von −49 % auf −38 % bei fast gleicher Rendite (11,1 % statt 11,2 %), **ganz ohne Trading**.
4. Einschränkungen: Monatsdurchschnittskurse, USD statt EUR (Wechselkursrisiko fehlt), US-Markt im Rückblick besonders erfolgreich. Für Bitcoin gibt es noch keinen historischen Test.

---

## D. Projektplan

| Komponente | Status |
|---|---|
| Historische Daten + Validierung (`bii/historical.py`) | ✅ |
| Backtest-Engine mit Kosten, Verzögerung, Steuer-Szenario (`bii/backtest.py`) | ✅ getestet |
| Strategien T1–T3 (`bii/strategies.py`) | ✅ |
| Live-Daten aus mehreren Quellen mit Gegenprüfung (`bii/live_data.py`) | ✅ Code fertig; Live-Lauf über GitHub Actions |
| Risiko-Engine, Positionsgröße für 0,75 % Risiko (`bii/risk.py`) | ✅ |
| Fälschungssicheres Journal mit Hash-Kette (`bii/journal.py`) | ✅ getestet |
| Forward-Test FT1 + Tagesbericht (`bii/forward.py`, `scripts/daily_check.py`) | ✅ |
| Automatisierung + iPhone-Benachrichtigung (GitHub Actions + Issue) | ✅ angelegt, Zeitplan wartet auf Freigabe |
| Momentum-/Swing-Backtests mit Tagesdaten | ⏳ braucht Tagesdaten (über Actions oder freigegebene Domains) |
| Wochenbericht inkl. Nachrichtenrecherche durch Claude | ⏳ nach Freigabe |

**Kosten:** 0 € zusätzlich. GitHub Actions ist für öffentliche Repos kostenlos, für private Repos sind 2.000 Minuten im Monat frei (Bedarf ca. 30–60). Datenquellen sind kostenlos. Claude Pro ist vorhanden. **Claude Max ist für diesen Ablauf nicht nötig.**

---

## Quellen (Claude-Funktionen)
- Anthropic Help Center: https://support.claude.com/en/articles/13947068
- Cowork auf iPhone/iPad/Web: https://www.apfelpatient.de/en/news/claude-cowork-iphone-ipad-web
- Geplante Aufgaben in Cowork: https://the-decoder.com/claudes-cowork-desktop-app-now-runs-scheduled-tasks-so-your-ai-assistant-works-while-you-sleep/
- Netzwerkeinstellungen der Cloud-Umgebung: https://code.claude.com/docs/en/cloud-environments#network-access
- Daten: https://github.com/datasets/s-and-p-500 (R. Shiller), https://github.com/datasets/gold-prices
