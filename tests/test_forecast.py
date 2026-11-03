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
from bii.forecast import evaluate, jr, quality, report  # noqa: E402

PINS = {1: ('CLAUDE-2026-11-03-SPX-001', '791c8a25d676efe8e9f26174a8f34625877d9a2c8d8078442f87d63cf9f7400e'), 2: ('CLAUDE-2026-11-03-NDX-002', '55cf4218d5f8e9ae9b491647b615465d391ddd470b3abb8953fa613b742ee429'), 3: ('CLAUDE-2026-11-03-DJI-003', '25764af9e9778ae2472ed5b5f4ec7869f22f3d73a34bff4d5811462491cfdf5f'), 4: ('CLAUDE-2026-11-03-RUT-004', '941148b808d9502f4454269276b33a7a62bd0d6c7b81a2dcc7c15908be3db929')}   # festgeschriebene Hashes der ersten Claude-Prognosen (03.11.2026, vor US-Eröffnung) – nie ändern

BASE = {"prognose_id": "T-1", "ki": "claude", "instrument": {"id": "X", "name": "X", "yahoo": "X", "venue": "XNYS"}, "trade_zulaessig": True, "order": {"limit": 101.0, "stop": 95.0, "ziel": 110.0},
        "referenz": {"kurs": 100.0, "waehrung": "USD", "datum": "2026-11-02", "quelle": ["q"]},
        "horizonte": {"1": {"tage": 1, "zieltermin": "2026-11-03", "erwartung_pct": 0.5, "p_positiv": 0.6},
                      "5": {"tage": 5, "zieltermin": "2026-11-09", "erwartung_pct": 1.0, "p_positiv": 0.6},
                      "20": {"tage": 20, "zieltermin": "2026-12-01", "erwartung_pct": 2.0, "p_positiv": 0.6}},
        "entscheidung": "KAUFEN", "gruende": "g", "gegenargumente": "c", "falsifikation": "f", "quellen": ["q"], "belastbarkeit": "eingeschraenkt"}
T0 = datetime(2026, 11, 3, 14, 0, tzinfo=timezone.utc)   # vor US-Eröffnung (14:30 UTC im Winter)


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
    wrong = copy.deepcopy(BASE); wrong["prognose_id"] = "T-4"; wrong["horizonte"]["20"]["zieltermin"] = "2026-12-02"
    with pytest.raises(ValueError):
        jr.add(wrong, now=T0, ki_path=jp)                                    # Zieltermin passt nicht zum Börsenkalender (Thanksgiving)
    stale = copy.deepcopy(BASE); stale["prognose_id"] = "T-5"; stale["referenz"]["datum"] = "2026-10-30"
    with pytest.raises(ValueError):
        jr.add(stale, now=T0, ki_path=jp)                                    # Informationsstichtag != letzter abgeschlossener Handelstag
    bad = copy.deepcopy(BASE); bad["prognose_id"] = "T-3"; del bad["falsifikation"]
    with pytest.raises(ValueError):
        jr.add(bad, now=T0, ki_path=jp)


def _qd(vals, sec=True, tier_frame=None):
    idx = pd.bdate_range("2025-06-02", periods=len(vals))
    df = pd.DataFrame({"open": vals, "high": [v * 1.001 for v in vals], "low": [v * 0.999 for v in vals], "close": vals, "volume": 1e6}, index=idx, dtype=float)
    q = quality.QualData("X", "XNYS", df, tier_frame or quality.B, [])
    if sec:
        q.secondary = {d: {k: float(df.loc[d, k]) for k in ("open", "high", "low", "close")} for d in df.index}
        q.secondary_name = "Test"
    return q


def _hist(end_vals):
    """Reihe, die am 2026-11-02 endet; davor 300 Handelstage Historie."""
    n = len(end_vals)
    idx = pd.bdate_range(end="2026-11-02", periods=300)
    base = [100.0] * 300
    return base, idx


def _data(path_vals, sec=True):
    """Kursreihe: 300 Handelstage bis 02.11.2026 (je 100) + path_vals ab 03.11.2026 (Handelstage laut Kalender)."""
    import exchange_calendars as xc
    hist = pd.bdate_range(end="2026-11-02", periods=300)
    cal = xc.get_calendar("XNYS")
    fut = cal.sessions_window(pd.Timestamp("2026-11-03"), len(path_vals))
    idx = hist.append(pd.DatetimeIndex(fut))
    vals = [100.0] * 300 + list(path_vals)
    df = pd.DataFrame({"open": vals, "high": [v * 1.001 for v in vals], "low": [v * 0.999 for v in vals], "close": vals, "volume": 1e6}, index=idx, dtype=float)
    q = quality.QualData("X", "XNYS", df, quality.B, [])
    if sec:
        q.secondary = {d: {k: float(df.loc[d, k]) for k in ("open", "high", "low", "close")} for d in df.index}
        q.secondary_name = "Test"
    return q


def test_evaluation_math_open_and_missing(tmp_path):
    (tmp_path / "prognosen.jsonl").write_text("")
    jr.add(copy.deepcopy(BASE), now=T0, ki_path=tmp_path / "prognosen.jsonl")
    path = [99, 101, 102, 103, 104, 105, 106, 107] + [108] * 15       # 03.11. ... (23 Handelstage)
    q = _data(path)
    new = evaluate.evaluate_ki("claude", lambda i: q, date(2026, 11, 4), base=tmp_path)
    assert len(new) == 1 and new[0]["ist_pct"] == -1.0 and new[0]["richtung_richtig"] is False
    assert new[0]["abweichung_pp"] == -1.5 and new[0]["brier"] == 0.36 and new[0]["entscheidung_sinnvoll"] is False
    assert new[0]["vergleich"]["null_abs_fehler_pp"] == 1.0 and "Richtung falsch" in new[0]["kritik"]
    new = evaluate.evaluate_ki("claude", lambda i: q, date(2026, 11, 10), base=tmp_path)
    assert [e["horizont"] for e in new] == [5] and new[0]["ist_pct"] == 4.0          # 5. Handelstag nach 02.11. = 09.11. (Kurs 104)
    assert evaluate.evaluate_ki("claude", lambda i: q, date(2026, 11, 10), base=tmp_path) == []
    st = evaluate.stats("claude", date(2026, 11, 10), base=tmp_path)["horizonte"]
    assert st[20]["offen"] == 1 and "trefferquote" not in st[20]
    assert st[1]["trefferquote"] == 0.0 and st[5]["trefferquote"] == 1.0
    new = evaluate.evaluate_ki("claude", lambda i: None, date(2026, 12, 20), base=tmp_path)
    assert [e["status"] for e in new] == ["nicht_auswertbar"]
    assert journal.verify(tmp_path / "bewertungen.jsonl")[0]


def test_bad_data_is_blocked_not_scored(tmp_path):
    jr.add(copy.deepcopy(BASE), now=T0, ki_path=tmp_path / "prognosen.jsonl")
    bad = _data([101, 102, 103, 104, 105, 106], sec=True)
    bad.frame_tier, bad.reasons = quality.C, ["inkonsistente OHLC-Balken"]
    assert evaluate.evaluate_ki("claude", lambda i: bad, date(2026, 11, 4), base=tmp_path) == []           # nicht bewertet, nicht als Warnung gezählt
    new = evaluate.evaluate_ki("claude", lambda i: bad, date(2026, 11, 20), base=tmp_path)             # nach Karenzzeit: nicht auswertbar mit Grund
    assert all(e["status"] == "nicht_auswertbar" and "Datenqualität" in e["grund"] for e in new) and new
    # Zweitquelle weicht ab -> Stufe C am betroffenen Tag
    dev = _data([101, 102, 103, 104, 105, 106])
    d = pd.Timestamp("2026-11-03"); dev.secondary[d]["close"] *= 1.1
    assert dev.tier_at(d) == quality.C and dev.tier_at(pd.Timestamp("2026-11-04")) == quality.A


def test_competition_phase_requires_tier_a(tmp_path):
    p = copy.deepcopy(BASE)
    jr.add(p, now=T0, ki_path=tmp_path / "prognosen.jsonl")
    single = _data([101, 102, 103, 104, 105, 106], sec=False)       # Stufe B
    assert evaluate.evaluate_ki("claude", lambda i: single, date(2026, 11, 4), base=tmp_path, phase_override="wettbewerb") == []
    assert len(evaluate.evaluate_ki("claude", lambda i: single, date(2026, 11, 4), base=tmp_path, phase_override="pilot")) == 1


def test_baselines_point_in_time(tmp_path):
    jr.add(copy.deepcopy(BASE), now=T0, ki_path=tmp_path / "prognosen.jsonl")
    q = _data([100.5, 101, 102, 103, 104, 105])
    e = evaluate.evaluate_ki("claude", lambda i: q, date(2026, 11, 4), base=tmp_path)[0]
    assert e["vergleich"]["null_abs_fehler_pp"] == 0.5 and "konstant_0_5_brier" in e["vergleich"]
    s = pd.Series([100.0 + (i % 3) for i in range(400)], index=pd.bdate_range("2025-01-01", periods=400))
    b = evaluate.baseline(s, s.index[300], 5)
    assert b["basis_beobachtungen"] == 296                          # nur Renditen, deren Ende <= Referenzdatum


def test_non_evaluated_decision_flag(tmp_path):
    p = copy.deepcopy(BASE); p["entscheidung_bewerten"] = False
    jr.add(p, now=T0, ki_path=tmp_path / "prognosen.jsonl")
    new = evaluate.evaluate_ki("claude", lambda i: _data([101, 102, 103, 104, 105, 106]), date(2026, 11, 4), base=tmp_path)
    assert new[0]["entscheidung_sinnvoll"] is None


def test_reports_render():
    today = date(2026, 11, 5)
    assert "Treffer Richtung" in report.stats_table("claude", today)
    assert "CLAUDE-2026-11-03-SPX-001" in report.forecasts_table("claude")
