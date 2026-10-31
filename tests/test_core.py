"""Technische Tests. Synthetische Kurse dienen NUR der Code-Prüfung, nie als Ergebnis."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bii import backtest as bt, forward, journal  # noqa: E402
from bii.live_data import UNIVERSE, PriceSeries  # noqa: E402
from bii.risk import RiskRules, position_size  # noqa: E402
from scripts.schedule_gate import decide  # noqa: E402

INST = {u.key: u for u in UNIVERSE}


def utc(s):
    return pd.Timestamp(s, tz="UTC")


def make_ps(key, idx, values, secondary="same", kind="unabhaengig"):
    s = pd.Series(values, index=idx, dtype=float)
    sec = s.copy() if isinstance(secondary, str) and secondary == "same" else secondary
    return PriceSeries(INST[key], s, "synthetisch", "t", {"ok": True}, [], sec, "synthetisch-2", kind, 0.015)


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    jp = tmp_path / "j.jsonl"
    monkeypatch.setattr(forward, "STATE", tmp_path / "state.json")
    monkeypatch.setattr(journal, "JOURNAL", jp)
    monkeypatch.setattr(journal.append, "__defaults__", (jp, None))
    monkeypatch.setattr(journal.read, "__defaults__", (jp,))
    monkeypatch.setattr(journal.verify, "__defaults__", (jp,))
    return jp


# ------------------------------------------------------------------ Grundbausteine
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
    idx = pd.date_range("2000-01-01", periods=600, freq="MS")
    r = pd.Series(np.random.default_rng(0).normal(0.005, 0.04, len(idx)), index=idx)
    rets = pd.DataFrame({"equity": r, "cash": 0.0})
    oracle = pd.DataFrame({"equity": (r > 0).astype(float)}, index=idx)
    oracle["cash"] = 1 - oracle["equity"]
    assert bt.run("o", rets, oracle, lag=0, cost_per_turnover=0).returns.mean() > 0.015
    assert abs(bt.run("o", rets, oracle, lag=1, cost_per_turnover=0).returns.mean()) < 0.01


# ------------------------------------------------------------------ Monatswechsel
def test_xetra_calendar():
    assert forward.expected_last_bar(pd.Period("2026-10"), "equity_etf") == pd.Timestamp("2026-10-30")  # 31. = Samstag
    assert forward.expected_last_bar(pd.Period("2026-10"), "crypto") == pd.Timestamp("2026-10-31")
    assert forward.expected_last_bar(pd.Period("2026-12"), "equity_etf") == pd.Timestamp("2026-12-30")  # 31.12. geschlossen
    assert forward.expected_last_bar(pd.Period("2024-03"), "equity_etf") == pd.Timestamp("2024-03-28")  # Karfreitag 29.03.2024
    assert forward._easter(2026).isoformat() == "2026-04-05"


def test_last_completed_month_uses_berlin_time():
    # 31.10. 23:30 UTC = 1.11. 00:30 Berlin -> Oktober abgeschlossen
    assert str(forward.last_completed_month(utc("2026-10-31 23:30"))) == "2026-10"
    assert str(forward.last_completed_month(utc("2026-10-31 11:00"))) == "2026-09"


def test_complete_bars_crypto_and_etf():
    idx = pd.date_range("2026-10-25", "2026-11-02")
    btc = make_ps("BTC", idx, np.arange(len(idx)) + 100.0)
    # Montag 2.11. 17:40 UTC: laufender UTC-Tag 2.11. ist unvollständig
    assert btc.complete(utc("2026-11-02 17:40")).index[-1] == pd.Timestamp("2026-11-01")
    etf = make_ps("WORLD", pd.bdate_range("2026-10-26", "2026-11-02"), np.arange(6) + 100.0)
    assert etf.complete(utc("2026-11-02 15:00")).index[-1] == pd.Timestamp("2026-10-30")   # 16:00 Berlin
    assert etf.complete(utc("2026-11-02 17:40")).index[-1] == pd.Timestamp("2026-11-02")   # 18:40 Berlin


def test_october_close_etf_vs_btc():
    """Am Samstag 31.10. ist Oktober noch nicht abgeschlossen; am Montag 2.11. 18:40 schon –
    ETF-Monatsschluss = Fr 30.10., Bitcoin-Monatsschluss = Sa 31.10."""
    days = pd.date_range("2025-06-01", "2026-11-02")
    btc = make_ps("BTC", days, np.linspace(50, 80, len(days)))
    bd = pd.bdate_range("2025-06-02", "2026-11-02")
    etf = make_ps("WORLD", bd, np.linspace(100, 130, len(bd)))
    sat = utc("2026-10-31 16:40")
    assert forward.month_check(etf, sat)["monat"] == "2026-09"
    mon = utc("2026-11-02 17:40")
    m_etf, m_btc = forward.month_check(etf, mon), forward.month_check(btc, mon)
    assert m_etf["ok"] and m_etf["erwarteter_letzter_kurstag"] == "2026-10-30"
    assert m_btc["ok"] and m_btc["erwarteter_letzter_kurstag"] == "2026-10-31"
    sig = forward.trend_signal(btc.complete(mon), pd.Period("2026-10"))
    assert sig["monat"] == "2026-10" and sig["monatsschluss"] == round(float(btc.close.loc["2026-10-31"]), 4)


def test_month_check_rejects_missing_or_unverified_close():
    bd = pd.bdate_range("2025-06-02", "2026-11-02")
    gap = make_ps("WORLD", bd.drop(pd.Timestamp("2026-10-30")), np.linspace(100, 130, len(bd) - 1))
    assert not forward.month_check(gap, utc("2026-11-02 17:40"))["ok"]
    no_sec = make_ps("WORLD", bd, np.linspace(100, 130, len(bd)), secondary=None)
    assert not forward.month_check(no_sec, utc("2026-11-02 17:40"))["ok"]


# ------------------------------------------------------------------ Ausführung nur auf geprüfter Basis
def _universe(end="2026-11-03", secondary_bad_on=None):
    days = pd.date_range("2025-06-01", end)
    bd = pd.bdate_range("2025-06-02", end)
    out = {}
    for key, idx, vals in (("WORLD", bd, np.linspace(100, 130, len(bd))),
                           ("GOLD", bd, np.linspace(130, 100, len(bd))),
                           ("BTC", days, np.linspace(50, 80, len(days)))):
        sec = pd.Series(vals, index=idx)
        if secondary_bad_on is not None:
            sec = sec.copy(); sec.loc[pd.Timestamp(secondary_bad_on)] *= 1.10
        out[key] = make_ps(key, idx, vals, secondary=sec)
    return out


def test_forward_signals_and_verified_execution(sandbox):
    out = forward.step(_universe(), utc("2026-11-02 17:40"))
    acts = {(e["portfolio"], e["asset"]): e["aktion"] for e in out["events"] if e["typ"] == "signal"}
    assert acts == {("BENCH", "WORLD"): "KAUF", ("TREND", "WORLD"): "KAUF",
                    ("TREND", "GOLD"): "HALTEN", ("TREND", "BTC"): "KAUF"}
    assert all(e["daten"]["monat"] in ("start", "2026-10") for e in out["events"])
    # Signale entstehen 2.11. -> Ausführung frühestens am Schluss 3.11. (ETF) bzw. UTC-Tag 3.11. (BTC)
    out2 = forward.step(_universe(), utc("2026-11-03 17:40"))
    ex = {e["asset"]: e["kursdatum"] for e in out2["events"] if e["typ"] == "ausfuehrung"}
    assert ex == {"WORLD": "2026-11-03"}                       # BTC-Tag 3.11. ist noch nicht abgeschlossen
    out3 = forward.step(_universe("2026-11-04"), utc("2026-11-04 17:40"))
    ex3 = {e["asset"]: e["kursdatum"] for e in out3["events"] if e["typ"] == "ausfuehrung"}
    assert ex3 == {"BTC": "2026-11-03"}
    assert not out3["state"]["pending"] and journal.verify()[0]


def test_no_execution_on_unverified_price(sandbox):
    forward.step(_universe(), utc("2026-11-02 17:40"))
    out = forward.step(_universe(secondary_bad_on="2026-11-03"), utc("2026-11-03 17:40"))
    assert not [e for e in out["events"] if e["typ"] == "ausfuehrung"]
    assert out["blocked"] and "nicht bestätigt" in out["blocked"][0]["blockiert_grund"]
    # Fehlende Daten: keine Ausführung, Bewertung mit letztem bekannten Kurs
    out2 = forward.step({}, utc("2026-11-03 18:00"))
    assert not [e for e in out2["events"] if e["typ"] == "ausfuehrung"] and out2["blocked"]


def test_no_signal_without_verified_month_close(sandbox):
    u = _universe()
    u["BTC"].secondary = None
    out = forward.step(u, utc("2026-11-02 17:40"))
    assert ("TREND", "BTC") not in {(e["portfolio"], e["asset"]) for e in out["events"]}
    assert any(d["asset"] == "BTC" for d in out["deferred"])


def test_verify_proxy_ratio():
    bd = pd.bdate_range("2026-01-01", "2026-11-02")
    gold_g = pd.Series(np.linspace(100, 120, len(bd)), index=bd)
    proxy = gold_g * 31.1035 * 1.004       # anderer Maßstab, stabiles Verhältnis
    ps = PriceSeries(INST["GOLD"], gold_g, "x", "t", {}, [], proxy, "paxg", "proxy", 0.025)
    assert ps.verify(bd[-1])["ok"]
    proxy2 = proxy.copy(); proxy2.iloc[-1] *= 1.05
    ps.secondary = proxy2
    assert not ps.verify(bd[-1])["ok"]


# ------------------------------------------------------------------ Zeitplan (Sommer-/Winterzeit)
def test_schedule_gate_dst():
    winter = datetime(2026, 11, 2, 17, 45, tzinfo=timezone.utc)   # Mo, MEZ
    assert decide("schedule", "40 17 * * 1-5", winter, None)[0]
    assert not decide("schedule", "40 16 * * 1-5", winter, None)[0]
    summer = datetime(2027, 6, 7, 16, 50, tzinfo=timezone.utc)   # Mo, MESZ
    assert decide("schedule", "40 16 * * 1-5", summer, None)[0]
    assert not decide("schedule", "40 17 * * 1-5", summer, None)[0]
    assert not decide("schedule", "40 17 * * 1-5", winter, "2026-11-02")[0]   # kein Doppellauf
    # Umstellungstag 29.03.2027 (Mo nach Sommerzeitbeginn)
    assert decide("schedule", "40 16 * * 1-5", datetime(2027, 3, 29, 16, 41, tzinfo=timezone.utc), None)[0]
    assert decide("workflow_dispatch", "", winter, "2026-11-02")[0]
