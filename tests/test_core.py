"""Technische Tests. Synthetische Kurse dienen NUR der Code-Prüfung, nie als Ergebnis."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bii import backtest as bt, forward, journal, strategies as st  # noqa: E402
from bii.live_data import UNIVERSE, PriceSeries  # noqa: E402
from bii.risk import RiskRules, position_size  # noqa: E402


def test_journal_tamper_detection(tmp_path):
    p = tmp_path / "j.jsonl"
    journal.append({"typ": "signal", "x": 1}, p)
    journal.append({"typ": "signal", "x": 2}, p)
    assert journal.verify(p)[0]
    lines = p.read_text().splitlines()
    e = json.loads(lines[0]); e["x"] = 99
    p.write_text(json.dumps(e) + "\n" + lines[1] + "\n")
    assert not journal.verify(p)[0]


def test_position_size_respects_budget():
    r = RiskRules()
    ps = position_size(10_000, entry=100, stop=92, rules=r)
    assert ps["max_verlust_bis_stop"] <= 75.0 + 1e-9
    assert ps["gewicht"] <= r.max_single_stock_weight


def test_no_lookahead():
    """Ein 'Orakel'-Signal (kennt die Rendite derselben Periode) darf durch lag>=1 keinen Vorteil haben."""
    idx = pd.date_range("2000-01-01", periods=600, freq="MS")
    rng = np.random.default_rng(0)
    r = pd.Series(rng.normal(0.005, 0.04, len(idx)), index=idx)
    rets = pd.DataFrame({"equity": r, "cash": 0.0})
    oracle = pd.DataFrame({"equity": (r > 0).astype(float)}, index=idx)
    oracle["cash"] = 1 - oracle["equity"]
    res0 = bt.run("o", rets, oracle, lag=0, cost_per_turnover=0)
    res1 = bt.run("o", rets, oracle, lag=1, cost_per_turnover=0)
    assert res0.returns.mean() > 0.015          # Orakel ohne lag: unrealistisch gut
    assert abs(res1.returns.mean()) < 0.01      # mit lag verschwindet der Vorteil


def test_forward_step(tmp_path, monkeypatch):
    monkeypatch.setattr(forward, "STATE", tmp_path / "state.json")
    monkeypatch.setattr(journal, "JOURNAL", tmp_path / "j.jsonl")
    monkeypatch.setattr(journal.append, "__defaults__", (tmp_path / "j.jsonl",))
    monkeypatch.setattr(journal.read, "__defaults__", (tmp_path / "j.jsonl",))
    idx = pd.bdate_range("2025-01-01", "2026-11-03")
    series = {}
    for i, inst in enumerate([u for u in UNIVERSE if u.key in ("WORLD", "GOLD", "BTC")]):
        trend = np.linspace(100, 150 if i != 1 else 80, len(idx))
        series[inst.key] = PriceSeries(inst, pd.Series(trend, index=idx), "synthetisch", "t", {"ok": True})
    out = forward.step(series, pd.Timestamp("2026-11-02"))
    acts = {(e["portfolio"], e["asset"]): e["aktion"] for e in out["events"] if e["typ"] == "signal"}
    assert acts[("BENCH", "WORLD")] == "KAUF"
    assert acts[("TREND", "WORLD")] == "KAUF"
    assert acts[("TREND", "GOLD")] == "HALTEN"   # fallender Trend, nicht gehalten -> nichts tun
    assert len(out["state"]["pending"]) == 3
    # nächster Lauf: Orders werden zum Schluss NACH Signalerstellung ausgeführt
    import datetime as dt
    out2 = forward.step(series, pd.Timestamp("2026-11-03"))
    # Signalerstellung ist 'heute' (echte Uhr) -> Ausführung erst, wenn ein späterer Kurs existiert
    created = pd.Timestamp(dt.date.today())
    expected_exec = 3 if idx[-1] > created else 0
    assert len([e for e in out2["events"] if e["typ"] == "ausfuehrung"]) == expected_exec
    assert journal.verify(tmp_path / "j.jsonl")[0]
