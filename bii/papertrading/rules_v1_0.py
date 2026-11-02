"""Handelsregeln Paper-Trading v1.0 (Swing-Trading, nur Long, nur virtuell).

EINGEFROREN: Diese Datei wird nach Teststart NICHT mehr verändert (SHA-256 in tests/test_papertrading.py
festgeschrieben). Änderungen an der Strategie = neue Datei rules_v1_1.py + neuer Registry-Eintrag +
eigener Ordner papertrading/v1.1/ (prospektiv, getrennt von v1.0).
Alle Entscheidungen nutzen ausschließlich Tagesbalken bis einschließlich zum Entscheidungstag.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

VERSION = "1.0"
START = "2026-11-02"           # erster Handelstag des Tests
END = "2027-01-24"             # letzter Kalendertag der ersten Testphase
CAPITAL_EUR = 10_000.0

# Beobachtungsuniversum: feste Liste liquider US-Standardwerte (vor Teststart festgelegt, nicht
# nach Ergebnissen angepasst). Handel in USD, Konto in EUR.
UNIVERSE = ("AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "AVGO", "TSLA", "LLY", "JPM",
            "V", "MA", "UNH", "XOM", "COST", "WMT", "HD", "PG", "NFLX", "ORCL",
            "AMD", "CRM", "ADBE", "KO", "PEP", "MRK", "ABBV", "CAT", "GE", "TMO")
REGIME = "SPY"                 # Marktfilter und Referenz für relative Stärke (wird nicht gehandelt)
BENCH = {"symbol": "EUNL.DE", "name": "iShares Core MSCI World UCITS ETF (Acc), IE00B4L5Y983", "currency": "EUR"}

PARAMS = {
    # --- Signal ---
    "sma_fast": 50, "sma_slow": 200, "regime_sma": 100,
    "breakout_days": 20, "volume_factor": 1.2, "volume_days": 20,
    "rsi_min": 50.0, "rsi_max": 78.0,
    "atr_days": 14, "atr_pct_min": 0.01, "atr_pct_max": 0.06,
    "min_dollar_volume": 100e6,
    "rs_days": 60,
    "event_gap_max": 0.08,         # |Tagesbewegung| > 8 % = Ereignistag -> kein Einstieg
    "min_bars": 210,
    # --- Order / Exit ---
    "limit_gap": 0.01,             # Kauflimit = Schlusskurs + 1 %
    "stop_atr": 2.0, "target_r": 2.5, "breakeven_r": 1.0, "max_hold_days": 20,
    # --- Risiko ---
    "risk_per_trade": 0.01, "max_positions": 5, "max_new_per_day": 2,
    "max_position_weight": 0.20, "min_position_eur": 300.0,
    "drawdown_pause": 0.10, "leverage": False,
    # --- Kosten-/Ausführungsannahmen (Annahmen, keine Brokerzusage) ---
    "fee_eur": 1.0, "half_spread": 0.0005, "slippage": 0.0005, "fx_fee": 0.0025,
    "reject_rate": 0.02,           # deterministisch simulierte Ablehnung (Hash der Order-ID)
    "crosscheck_tol": 0.02,
    "news_days": 3,
}
NEG_NEWS = ("probe", "investigation", "lawsuit", "sued", "fraud", "subpoena", "recall", "sanction", "bankruptcy",
            "downgrade", "guidance cut", "cuts guidance", "resigns", "short seller", "sec charges", "plunge", "halt")


def _rsi(close: pd.Series, n: int = 14) -> pd.Series:
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def _atr(df: pd.DataFrame, n: int) -> pd.Series:
    pc = df["close"].shift()
    tr = pd.concat([df["high"] - df["low"], (df["high"] - pc).abs(), (df["low"] - pc).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean()


def regime_ok(spy: pd.DataFrame, d) -> tuple[bool, dict]:
    s = spy.loc[:d, "close"]
    p = PARAMS
    if len(s) < p["regime_sma"]:
        return False, {"grund": "zu wenig SPY-Historie"}
    sma = float(s.tail(p["regime_sma"]).mean())
    return bool(s.iloc[-1] > sma), {"spy_close": round(float(s.iloc[-1]), 2), f"spy_sma{p['regime_sma']}": round(sma, 2)}


def evaluate(df: pd.DataFrame, spy: pd.DataFrame, d) -> dict:
    """Prüft alle Einstiegsregeln mit Daten bis einschließlich d. Rückgabe: ok, gruende, kennzahlen, score."""
    p = PARAMS
    df = df.loc[:d]
    if len(df) < p["min_bars"] or df.index[-1] != pd.Timestamp(d):
        return {"ok": False, "gruende": ["zu wenig Daten oder kein Balken am Entscheidungstag"], "kennzahlen": {}, "score": 0.0}
    c = df["close"]
    last = float(c.iloc[-1])
    sma_f, sma_s = float(c.tail(p["sma_fast"]).mean()), float(c.tail(p["sma_slow"]).mean())
    prior_high = float(df["high"].iloc[-1 - p["breakout_days"]:-1].max())
    vol_ratio = float(df["volume"].iloc[-1] / df["volume"].iloc[-1 - p["volume_days"]:-1].mean())
    rsi = float(_rsi(c).iloc[-1])
    atr = float(_atr(df, p["atr_days"]).iloc[-1])
    dollar_vol = float((df["close"] * df["volume"]).tail(20).mean())
    ret_d = float(c.iloc[-1] / c.iloc[-2] - 1)
    rs = float(c.iloc[-1] / c.iloc[-1 - p["rs_days"]] - 1)
    spy_c = spy.loc[:d, "close"]
    rs_rel = rs - float(spy_c.iloc[-1] / spy_c.iloc[-1 - p["rs_days"]] - 1)
    k = {"schluss": round(last, 2), f"sma{p['sma_fast']}": round(sma_f, 2), f"sma{p['sma_slow']}": round(sma_s, 2),
         "hoch_20t_vorher": round(prior_high, 2), "volumen_faktor": round(vol_ratio, 2), "rsi14": round(rsi, 1),
         "atr14": round(atr, 2), "atr_pct": round(atr / last, 4), "dollarvolumen_20t_mio": round(dollar_vol / 1e6, 0),
         "tagesbewegung": round(ret_d, 4), "rel_staerke_60t": round(rs_rel, 4)}
    checks = [
        (last > sma_f > sma_s, "Trend: Schluss > SMA50 > SMA200"),
        (last > prior_high, "Ausbruch über 20-Tage-Hoch"),
        (vol_ratio >= p["volume_factor"], f"Volumen >= {p['volume_factor']}x Durchschnitt"),
        (p["rsi_min"] <= rsi <= p["rsi_max"], "RSI im Fenster"),
        (p["atr_pct_min"] <= atr / last <= p["atr_pct_max"], "ATR-Spanne"),
        (dollar_vol >= p["min_dollar_volume"], "Liquidität"),
        (rs_rel > 0, "relative Stärke gegenüber SPY"),
        (abs(ret_d) <= p["event_gap_max"], "kein Ereignistag (Kurssprung)"),
    ]
    failed = [t for ok, t in checks if not ok]
    score = rs_rel + 0.1 * min(vol_ratio, 3.0)
    return {"ok": not failed, "gruende": failed or [t for _, t in checks], "kennzahlen": k, "score": round(score, 4), "atr": atr}
