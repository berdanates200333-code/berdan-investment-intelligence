"""Tests Prognosesystem: Journal-Unveränderlichkeit, Pflichtfelder, Auswertung, Portfolio-Regeln."""
import copy
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bii import journal  # noqa: E402
from bii.forecast import evaluate, jr, portfolio, report  # noqa: E402

PINS = {1: ('CLAUDE-2026-11-03-SPX-001', '791c8a25d676efe8e9f26174a8f34625877d9a2c8d8078442f87d63cf9f7400e'), 2: ('CLAUDE-2026-11-03-NDX-002', '55cf4218d5f8e9ae9b491647b615465d391ddd470b3abb8953fa613b742ee429'), 3: ('CLAUDE-2026-11-03-DJI-003', '25764af9e9778ae2472ed5b5f4ec7869f22f3d73a34bff4d5811462491cfdf5f'), 4: ('CLAUDE-2026-11-03-RUT-004', '941148b808d9502f4454269276b33a7a62bd0d6c7b81a2dcc7c15908be3db929')}   # festgeschriebene Hashes der ersten Claude-Prognosen (03.11.2026, vor US-Eröffnung) – nie ändern

BASE = {"prognose_id": "T-1", "ki": "claude", "instrument": {"id": "X", "name": "X", "yahoo": "X"}, "trade_zulaessig": True,
        "referenz": {"kurs": 100.0, "waehrung": "USD", "datum": "2026-11-02", "quelle": ["q"]},
        "horizonte": {"1": {"tage": 1, "zieltermin": "2026-11-03", "erwartung_pct": 0.5, "p_positiv": 0.6},
                      "5": {"tage": 5, "zieltermin": "2026-11-09", "erwartung_pct": 1.0, "p_positiv": 0.6},
                      "20": {"tage": 20, "zieltermin": "2026-12-01", "erwartung_pct": 2.0, "p_positiv": 0.6}},
        "entscheidung": "KAUFEN", "gruende": "g", "gegenargumente": "c", "falsifikation": "f", "quellen": ["q"], "belastbarkeit": "eingeschraenkt"}
T0 = datetime(2026, 11, 3, 14, 0, tzinfo=timezone.utc)


def test_real_claude_journal_intact_and_pinned():
    p = jr.path("claude")
    assert journal.verify(p)[0]
    lines = [json.loads(x) for x in p.read_text().splitlines()]
    for seq, (pid, h) in PINS.items():
        e = lines[int(seq) - 1]
        assert e["prognose_id"] == pid and e["hash"] == h, f"Prognose {pid} wurde verändert"


def test_add_computes_target_and_blocks_duplicates_and_late(tmp_path):
    jp = tmp_path / "p.jsonl"
    e = jr.add(copy.deepcopy(BASE), now=T0, ki_path=jp)
    assert e["horizonte"]["5"]["zielkurs"] == 101.0 and e["regelversion"] == jr.REGELVERSION
    with pytest.raises(ValueError):
        jr.add(copy.deepcopy(BASE), now=T0, ki_path=jp)           # kein Überschreiben
    late = copy.deepcopy(BASE); late["prognose_id"] = "T-2"
    with pytest.raises(ValueError):
        jr.add(late, now=datetime(2026, 11, 3, 15, 0, tzinfo=timezone.utc), ki_path=jp)   # nach Beginn des Bewertungszeitraums
    bad = copy.deepcopy(BASE); bad["prognose_id"] = "T-3"; del bad["falsifikation"]
    with pytest.raises(ValueError):
        jr.add(bad, now=T0, ki_path=jp)


def _series(vals):
    return pd.Series(vals, index=pd.bdate_range("2026-11-02", periods=len(vals)))


def test_evaluation_math_open_and_missing(tmp_path):
    (tmp_path / "prognosen.jsonl").write_text("")
    jr.add(copy.deepcopy(BASE), now=T0, ki_path=tmp_path / "prognosen.jsonl")
    s = _series([100, 99, 101, 102, 103, 104, 105, 106])     # 02.11. ... 11.11.
    # 04.11.: nur 1-Tages-Ziel fällig
    new = evaluate.evaluate_ki("claude", lambda x: s, date(2026, 11, 4), base=tmp_path)
    assert len(new) == 1 and new[0]["ist_pct"] == -1.0 and new[0]["richtung_richtig"] is False
    assert new[0]["abweichung_pp"] == -1.5 and new[0]["brier"] == 0.36 and new[0]["entscheidung_sinnvoll"] is False
    assert "Richtung falsch" in new[0]["kritik"]
    # später: 5-Tage fällig, 20-Tage bleibt offen; keine Doppelbewertung
    new = evaluate.evaluate_ki("claude", lambda x: s, date(2026, 11, 10), base=tmp_path)
    assert [e["horizont"] for e in new] == [5] and new[0]["ist_pct"] == 4.0
    assert evaluate.evaluate_ki("claude", lambda x: s, date(2026, 11, 10), base=tmp_path) == []
    st = evaluate.stats("claude", date(2026, 11, 10), base=tmp_path)["horizonte"]
    assert st[20]["offen"] == 1 and st[20]["abgeschlossen"] == 0 and "trefferquote" not in st[20]   # offene verfälschen nichts
    assert st[1]["trefferquote"] == 0.0 and st[5]["trefferquote"] == 1.0
    # Datenmangel nach Karenzzeit -> nicht auswertbar
    new = evaluate.evaluate_ki("claude", lambda x: None, date(2026, 12, 20), base=tmp_path)
    assert [e["status"] for e in new] == ["nicht_auswertbar"]
    assert journal.verify(tmp_path / "bewertungen.jsonl")[0]


def test_non_evaluated_decision_flag(tmp_path):
    p = copy.deepcopy(BASE); p["entscheidung_bewerten"] = False
    jr.add(p, now=T0, ki_path=tmp_path / "prognosen.jsonl")
    new = evaluate.evaluate_ki("claude", lambda x: _series([100, 101, 102, 103, 104, 105]), date(2026, 11, 4), base=tmp_path)
    assert new[0]["entscheidung_sinnvoll"] is None


def test_portfolio_rules(tmp_path):
    pj, hj = tmp_path / "p.jsonl", tmp_path / "h.jsonl"
    jr.add(copy.deepcopy(BASE), now=T0, ki_path=pj)
    later = datetime(2026, 11, 3, 15, 0, tzinfo=timezone.utc)
    with pytest.raises(ValueError):
        portfolio.trade("claude", "kauf", "T-1", 100, 100.0, "q", 1.1, now=later, hj=hj, pj=pj)          # > 25 % / Barmittel
    e = portfolio.trade("claude", "kauf", "T-1", 20, 100.0, "q", 1.1, now=later, hj=hj, pj=pj)
    assert e["kosten_eur"] > 1.0 and portfolio.state("claude", hj)["cash_eur"] < 10_000 - 20 * 100 / 1.1
    with pytest.raises(ValueError):
        portfolio.trade("claude", "verkauf", "T-1", 50, 100.0, "q", 1.1, now=later, hj=hj, pj=pj)       # Leerverkauf
    with pytest.raises(ValueError):
        portfolio.trade("claude", "kauf", "T-1", 1, 100.0, "q", 1.1, now=T0, hj=hj, pj=pj)               # Trade vor Prognose
    v = portfolio.valuation("claude", {"X": 100.0}, 1.1, hj)
    assert v["gesamt_eur"] < 10_000 and not v["kurse_fehlen"]


def test_reports_render():
    today = date(2026, 11, 5)
    assert "Trefferquote" in report.stats_table("claude", today)
    assert "CLAUDE-2026-11-03-SPX-001" in report.forecasts_table("claude")
