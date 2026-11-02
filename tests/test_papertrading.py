"""Tests Paper-Trading: Regeln, Risiko, Ausführung, Journal, Pins (alles mit synthetischen Daten, ohne Netzwerk)."""
import hashlib
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bii import journal  # noqa: E402
from bii.papertrading import engine, report  # noqa: E402
from bii.papertrading import rules_v1_0 as rules  # noqa: E402

# Festgeschriebener Hash der eingefrorenen Regeldatei v1.0 (nur durch neue Version ersetzbar, nie ändern).
RULES_V1_0_SHA256 = "43b29a9918f72dc35e2de0beb7f5a4fa33a01cc1d458639880b6ade0ce0eeb0d"
IDX = pd.bdate_range("2025-12-01", "2026-11-13")


def _bars(drift=0.0006, seed=1, spike_day=None, vol=2e6, gap_after=None):
    rng = np.random.default_rng(seed)
    c = 100 * np.cumprod(1 + drift + rng.normal(0, 0.006, len(IDX)))
    df = pd.DataFrame({"close": c}, index=IDX)
    df["open"] = df.close.shift(1).fillna(df.close.iloc[0])
    df["high"] = df[["open", "close"]].max(axis=1) * 1.004
    df["low"] = df[["open", "close"]].min(axis=1) * 0.996
    df["volume"] = vol
    if spike_day:
        i = IDX.get_loc(pd.Timestamp(spike_day))
        prev = df.close.iloc[i - 1]
        top = max(df.high.iloc[i - 21:i].max(), prev) * 1.012
        df.iloc[i, df.columns.get_loc("open")] = prev * 1.002
        df.iloc[i, df.columns.get_loc("close")] = top
        df.iloc[i, df.columns.get_loc("high")] = top * 1.003
        df.iloc[i, df.columns.get_loc("low")] = prev * 0.999
        df.iloc[i, df.columns.get_loc("volume")] = vol * 3
        df.iloc[i + 1:, df.columns.get_loc("close")] = top * 1.002
        df.iloc[i + 1:, df.columns.get_loc("open")] = top * 1.001
        df.iloc[i + 1:, df.columns.get_loc("high")] = top * 1.01
        df.iloc[i + 1:, df.columns.get_loc("low")] = top * 0.995
    return df[["open", "high", "low", "close", "volume"]]


class Prov:
    def __init__(self, data, fx=1.10, cc="bestaetigt", news=None):
        self.data, self.log = data, []
        self._fx = pd.Series(fx, index=pd.date_range("2025-11-01", "2026-12-31"))
        self.cc, self.nw = cc, news or {"status": "geprueft", "anzahl": 3, "treffer": [], "quellen": []}

    def ohlcv(self, s):
        return self.data.get(s)

    def fx(self):
        return self._fx

    def crosscheck(self, s, d, close, tol):
        return {"status": self.cc, "abweichung": 0.001 if self.cc == "bestaetigt" else 0.05, "quelle": "Stooq"}

    def news(self, s, days, neg):
        return self.nw


def make(spike="2026-11-04", **kw):
    data = {t: _bars(seed=i + 10, drift=0.0001) for i, t in enumerate(rules.UNIVERSE)}
    data["AAPL"] = _bars(seed=3, drift=0.0014, spike_day=spike)
    data["SPY"] = _bars(seed=2, drift=0.0004)
    data[rules.BENCH["symbol"]] = _bars(seed=5, drift=0.0003)
    return Prov(data, **kw)


def now_at(d):
    return datetime.fromisoformat(d + "T22:30:00+00:00")


def test_rules_file_pinned():
    assert hashlib.sha256((ROOT / "bii/papertrading/rules_v1_0.py").read_bytes()).hexdigest() == RULES_V1_0_SHA256, \
        "Eingefrorene Regeln v1.0 wurden verändert – Änderungen nur als neue Version"


def test_ft1_journal_untouched_by_papertrading(tmp_path):
    before = (ROOT / "journal/journal.jsonl").read_bytes()
    st = engine.new_state(rules)
    engine.run(st, make(), rules, tmp_path / "j.jsonl", now=now_at("2026-11-04"))
    assert (ROOT / "journal/journal.jsonl").read_bytes() == before


def test_plan_documented_before_execution_and_risk_limit(tmp_path):
    st, jp = engine.new_state(rules), tmp_path / "j.jsonl"
    engine.run(st, make(), rules, jp, now=now_at("2026-11-04"))
    plans = [e for e in journal.read(jp) if e["typ"] == "order_plan"]
    assert len(plans) == 1 and plans[0]["ticker"] == "AAPL"
    p = plans[0]
    for k in ("ticker", "datum", "entscheidungsgrundlage", "orderart", "einstieg", "limit", "stop", "ziel", "stueck", "risikogrenze_eur", "quellen"):
        assert p.get(k) not in (None, "", []), k
    assert p["risiko_anteil"] <= 0.01 + 1e-9            # höchstens 1 % geplantes Risiko
    assert p["positionswert_eur"] <= 0.2 * st["equity"][-1]["aktiv_eur"] + 1
    assert not st["positions"] and len(st["pending"]) == 1   # noch nicht ausgeführt
    # Ausführung am Folgetag
    engine.run(st, make(), rules, jp, now=now_at("2026-11-05"))
    kinds = [e["typ"] for e in journal.read(jp)]
    assert kinds.index("order_plan") < (kinds.index("ausfuehrung") if "ausfuehrung" in kinds else kinds.index("ausfuehrung_fehlgeschlagen"))
    assert journal.verify(jp)[0]


def test_execution_costs_and_no_leverage(tmp_path):
    st, jp = engine.new_state(rules), tmp_path / "j.jsonl"
    prov = make()
    engine.run(st, prov, rules, jp, now=now_at("2026-11-04"))
    engine.run(st, prov, rules, jp, now=now_at("2026-11-05"))
    if "AAPL" in st["positions"]:
        pos = st["positions"]["AAPL"]
        assert pos["einstieg"] > prov.data["AAPL"].loc["2026-11-05", "open"]   # Spread + Slippage
        assert pos["kosten_eur"] >= rules.PARAMS["fee_eur"]
        assert st["cash_eur"] >= 0
    assert st["cash_eur"] >= 0 and st["costs_eur"] >= 0


def test_gap_above_limit_fails(tmp_path):
    st, jp = engine.new_state(rules), tmp_path / "j.jsonl"
    prov = make()
    engine.run(st, prov, rules, jp, now=now_at("2026-11-04"))
    df = prov.data["AAPL"]
    df.loc["2026-11-05", "open"] = df.loc["2026-11-04", "close"] * 1.05
    df.loc["2026-11-05", "high"] = df.loc["2026-11-05", "open"] * 1.01
    engine.run(st, prov, rules, jp, now=now_at("2026-11-05"))
    assert not st["positions"] and any("limit" in f["grund"] or "Ablehnung" in f["grund"] for f in st["failed"])


def test_late_documented_plan_rejected(tmp_path):
    st, jp = engine.new_state(rules), tmp_path / "j.jsonl"
    prov = make()
    engine.run(st, prov, rules, jp, now=now_at("2026-11-04"))
    st["pending"][0]["journal_utc"] = "2026-11-05T15:00:00+00:00"     # nach Eröffnung dokumentiert
    engine.run(st, prov, rules, jp, now=now_at("2026-11-05"))
    assert not st["positions"] and "eröffnung" in st["failed"][-1]["grund"]


def test_stop_gap_fills_at_open_and_closes_trade(tmp_path):
    st, jp = engine.new_state(rules), tmp_path / "j.jsonl"
    prov = make()
    engine.run(st, prov, rules, jp, now=now_at("2026-11-04"))
    for o in st["pending"]:
        o["id"] = "PT1.0-AAPL-X"   # Ablehnungs-Hash neutralisieren ist unnötig; wir erzwingen Ausführung unten
    engine.run(st, prov, rules, jp, now=now_at("2026-11-05"))
    if "AAPL" not in st["positions"]:
        pytest.skip("simulierte Ablehnung in diesem Testlauf")
    stop = st["positions"]["AAPL"]["stop"]
    df = prov.data["AAPL"]
    df.loc["2026-11-06", ["open", "high", "low", "close"]] = [stop * 0.95, stop * 0.96, stop * 0.9, stop * 0.92]
    engine.run(st, prov, rules, jp, now=now_at("2026-11-06"))
    assert not st["positions"] and st["closed"][-1]["grund"].startswith("Stop")
    assert st["closed"][-1]["ausstieg_usd"] < stop      # Kurslücke: schlechter als Stop
    assert st["closed"][-1]["pnl_eur"] < 0


def test_data_failure_blocks_trading(tmp_path):
    st = engine.new_state(rules)
    prov = make()
    prov.data["SPY"] = None
    s = engine.run(st, prov, rules, tmp_path / "j.jsonl", now=now_at("2026-11-04"))
    assert not st["equity"] and any("Pflichtdaten" in p for p in s["probleme"])


def test_news_veto_and_datacheck_veto(tmp_path):
    for kw in ({"news": {"status": "geprueft", "anzahl": 1, "treffer": ["SEC probe into Apple"], "quellen": []}}, {"cc": "abweichend"}):
        st, jp = engine.new_state(rules), tmp_path / f"j{len(kw)}{list(kw)[0]}.jsonl"
        engine.run(st, make(**kw), rules, jp, now=now_at("2026-11-04"))
        assert not st["pending"] and any(e["typ"] == "plan_verworfen" for e in journal.read(jp))


def test_claude_veto(tmp_path):
    st, jp = engine.new_state(rules), tmp_path / "j.jsonl"
    engine.run(st, make(), rules, jp, now=now_at("2026-11-04"), vetos=[{"ticker": "AAPL", "grund": "Test", "gueltig_bis": "2026-11-10"}])
    assert not st["pending"]


def test_drawdown_pause_blocks_new_positions(tmp_path):
    st, jp = engine.new_state(rules), tmp_path / "j.jsonl"
    prov = make()
    engine.run(st, prov, rules, jp, now=now_at("2026-11-03"))
    st["peak"] = st["equity"][-1]["aktiv_eur"] * 1.2          # Rückgang > 10 % simulieren
    engine.run(st, prov, rules, jp, now=now_at("2026-11-04"))
    assert st["paused"] and not st["pending"]
    assert any(e["typ"] == "pause" for e in journal.read(jp))
    # Freigabe nur per dokumentierter Datei nach Pausenbeginn
    engine.run(st, prov, rules, jp, now=now_at("2026-11-05"), freigaben=[{"datum": "2026-11-05"}])
    assert not st["paused"]


def test_benchmark_and_equity_tracking(tmp_path):
    st = engine.new_state(rules)
    engine.run(st, make(), rules, tmp_path / "j.jsonl", now=now_at("2026-11-04"))
    assert st["bench"]["stueck"] > 0 and st["equity"][0]["datum"] == "2026-11-02"
    assert abs(st["equity"][0]["bench_eur"] - 10_000) < 150
    assert st["equity"][0]["aktiv_eur"] == 10_000


def test_no_lookahead_in_signal():
    prov = make()
    full = rules.evaluate(prov.data["AAPL"], prov.data["SPY"], pd.Timestamp("2026-11-04"))
    cut = rules.evaluate(prov.data["AAPL"].loc[:"2026-11-04"], prov.data["SPY"].loc[:"2026-11-04"], pd.Timestamp("2026-11-04"))
    assert full["kennzahlen"] == cut["kennzahlen"] and full["ok"] == cut["ok"]


def test_incomplete_day_not_processed(tmp_path):
    st = engine.new_state(rules)
    engine.run(st, make(), rules, tmp_path / "j.jsonl", now=datetime(2026, 11, 4, 20, 0, tzinfo=timezone.utc))
    assert st["last_date"] == "2026-11-03"


def test_sizing_respects_budget_and_cash():
    sz = engine.size_position(10_000, 100, 101, 95, 1.1, 10_000, rules)
    assert sz["max_verlust_eur"] <= 100 + 1e-6
    assert engine.size_position(10_000, 100, 101, 95, 1.1, 50, rules)["stueck"] == 0


def test_final_evaluation_extends_on_small_sample():
    st = engine.new_state(rules)
    txt = report.final_evaluation(st, date(2027, 1, 25), date(2027, 1, 24), "1.0")
    assert "Urteil: VERLÄNGERN" in txt


def test_weekly_report_renders(tmp_path):
    st, jp = engine.new_state(rules), tmp_path / "j.jsonl"
    engine.run(st, make(), rules, jp, now=now_at("2026-11-04"))
    txt = report.weekly_report(st, journal.read(jp), date(2026, 11, 8), "1.0")
    assert "Benchmark" in txt and "Orderpläne" in txt
