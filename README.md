# berdan-investment-intelligence

Persönliches Research-Desk sowie regelbasiertes Backtest- und Forward-Test-System. **Nur virtuelles Kapital. Keine Echtgeld-Orders, keine Broker-Verbindung.**

- Aktueller Tagesbericht (FT1): [`reports/latest.md`](reports/latest.md) · Research-Monitor: [`reports/research/latest.md`](reports/research/latest.md)
- **Phase 2 – Research-Desk:** [`docs/PHASE2_RESEARCH_DESK.md`](docs/PHASE2_RESEARCH_DESK.md) · Profile: `research/db/companies/` · Thesen: `research/theses/` · KI-Analysen: `research/analyses/`
- **Phase 3 – Paper-Trading (virtuell):** [Strategie v1.0](docs/papertrading/STRATEGIE_v1.0.md) · [Status/Autonomie](docs/papertrading/PHASE3_STATUS.md) · [Tagesstand](reports/papertrading/latest.md) · [Wochenbericht](reports/papertrading/weekly/latest.md)
- **Prognosewettbewerb ChatGPT vs. Claude (Pilot, nicht gestartet):** [System & Regeln](docs/forecast/PROGNOSESYSTEM.md) · [Startschranke](forecast/wettbewerb_gate.json)
- Phase-1-Bericht: [`docs/PHASE1_BERICHT.md`](docs/PHASE1_BERICHT.md)
- Vorab festgelegtes Regelwerk: [`docs/REGELWERK_FT1.md`](docs/REGELWERK_FT1.md) (v1.0) · [`v1.1`](docs/REGELWERK_FT1_v1.1.md) · [`v1.2`](docs/REGELWERK_FT1_v1.2.md) · [Änderungen](docs/REGELWERK_AENDERUNGEN.md)
- Backtest-Ergebnisse: [`research/backtest_phase1.md`](research/backtest_phase1.md) · Szenarien: [`research/szenarien.md`](research/szenarien.md)
- Momentum-Forschung: [Plan](docs/research/MOMENTUM_PLAN.md) · [Ergebnis](research/momentum_m1_m3.md) · [Fazit](docs/research/MOMENTUM_FAZIT.md)
- Journal (append-only, Hash-Kette): [`journal/journal.jsonl`](journal/journal.jsonl)

## Aufbau
```
bii/historical.py   historische Daten laden und validieren
bii/backtest.py     Backtest mit Kosten, Ausführungsverzögerung, Steuer-Szenario
bii/strategies.py   Regelwerke (Trendfilter, Momentum, Tranchen)
bii/live_data.py    Tageskurse aus mehreren Quellen mit Gegenprüfung
bii/risk.py         Positionsgröße und Risikogrenzen
bii/journal.py      fälschungssicheres Handelsjournal
bii/forward.py      Forward-Test FT1 (virtuelle Portfolios)
scripts/            run_backtest.py · daily_check.py · scenarios.py
```

## Lokal ausführen
```
pip install -r requirements.txt
python -m pytest -q tests
python scripts/run_backtest.py
python scripts/daily_check.py   # braucht Internetzugang zu Yahoo/Stooq/CoinGecko
```

Keine Anlageberatung. Alle Ergebnisse sind Szenarien oder Simulationen.
