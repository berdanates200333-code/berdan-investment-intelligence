"""Phase 2, Aufgabe 6: Fehlerzähler je Instrument/Ursache, Proxy-Prüfstufe, veraltete Orders.
Berührt weder Journal noch Portfolio-Zustand."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bii.live_data import UNIVERSE, PriceSeries, _finish  # noqa: E402
from scripts.daily_check import dq_text, stale_pending_orders, update_counters  # noqa: E402

INST = {i.key: i for i in UNIVERSE}
NOW = pd.Timestamp("2026-11-02 17:45", tz="UTC")


def test_counters_separate_by_instrument_and_cause():
    ops = {}
    update_counters(ops, [("GOLD", "zweitquelle_fehlt", None), ("WORLD", "format", "Stooq")], NOW)
    active = update_counters(ops, [("GOLD", "zweitquelle_fehlt", None), ("WORLD", "veraltet", "Yahoo")], NOW)
    dp = ops["datenprobleme"]
    assert dp["GOLD|zweitquelle_fehlt"]["folge"] == 2 and active["GOLD|zweitquelle_fehlt"] == 2
    assert dp["WORLD|format"]["folge"] == 0 and dp["WORLD|format"]["gesamt"] == 1   # andere Ursache zählt getrennt
    assert dp["WORLD|veraltet"]["folge"] == 1


def test_proxy_is_plausibility_not_second_price():
    bd = pd.bdate_range("2026-01-01", "2026-10-30")
    gold = pd.Series(np.linspace(100, 120, len(bd)), index=bd)
    ps = PriceSeries(INST["GOLD"], gold, "Yahoo", "t", {}, [], gold * 31.1, "CoinGecko pax-gold (Proxy)", "proxy", 0.025)
    v = ps.verify(bd[-1])
    assert v["ok"] and v["stufe"] == "plausibilisiert" and v["zweitkurs"] is False
    _finish(ps, {**v, "art": "proxy"}, [], [])
    assert any(i["ursache"] == "nur_proxy_plausibilisiert" for i in ps.issues)
    assert "kein Zweitkurs" in dq_text(ps)
    direct = PriceSeries(INST["BTC"], gold, "Yahoo", "t", {}, [], gold * 1.001, "CoinGecko", "unabhaengig", 0.015)
    assert direct.verify(bd[-1])["stufe"] == "bestaetigt" and direct.verify(bd[-1])["zweitkurs"]


def test_stale_pending_order_detected():
    state = {"pending": [{"signal_id": "FT1-TREND-BTC-2026-09", "portfolio": "TREND", "asset": "BTC", "aktion": "KAUF"},
                         {"signal_id": "FT1-BENCH-WORLD-start", "portfolio": "BENCH", "asset": "WORLD", "aktion": "KAUF"}]}
    out = stale_pending_orders(state, NOW)
    assert [o["key"] for o in out] == ["FT1-TREND-BTC-2026-09"]          # Startsignal hat keinen Monat
    assert stale_pending_orders(state, pd.Timestamp("2026-10-31 12:00", tz="UTC")) == []   # Oktober noch offen


def test_heartbeat_detects_stale(tmp_path, monkeypatch):
    import json as _j
    from datetime import datetime, timedelta, timezone
    import scripts.heartbeat as hb
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    now = datetime(2026, 11, 3, 6, 35, tzinfo=timezone.utc)
    a.write_text(_j.dumps({"letzter_lauf_utc": (now - timedelta(days=1)).isoformat()}))
    b.write_text(_j.dumps({"letzter_erfolg_utc": (now - timedelta(hours=40)).isoformat()}))
    monkeypatch.setattr(hb, "ROOT", tmp_path)
    monkeypatch.setattr(hb, "CHECKS", [("M", a, "letzter_lauf_utc", timedelta(days=4)),
                                       ("R", b, "letzter_erfolg_utc", timedelta(hours=30))])
    p = hb.check(now)
    assert len(p) == 1 and p[0].startswith("R:")
