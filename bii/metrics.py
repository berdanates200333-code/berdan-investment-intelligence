"""Kennzahlen für Renditezeitreihen (exakte, reproduzierbare Berechnung)."""
from __future__ import annotations

import numpy as np
import pandas as pd


def equity_curve(returns: pd.Series, start: float = 1.0) -> pd.Series:
    return start * (1.0 + returns.fillna(0.0)).cumprod()


def max_drawdown(curve: pd.Series) -> float:
    peak = curve.cummax()
    return float((curve / peak - 1.0).min())


def longest_underwater(curve: pd.Series) -> int:
    """Längste Phase (in Perioden) unter dem bisherigen Höchststand."""
    under = curve < curve.cummax()
    longest = run = 0
    for u in under:
        run = run + 1 if u else 0
        longest = max(longest, run)
    return longest


def summarize(returns: pd.Series, periods_per_year: int = 12,
              cash_returns: pd.Series | None = None) -> dict:
    r = returns.dropna()
    n = len(r)
    if n == 0:
        return {}
    curve = equity_curve(r)
    years = n / periods_per_year
    cagr = curve.iloc[-1] ** (1 / years) - 1
    vol = r.std(ddof=1) * np.sqrt(periods_per_year)
    excess = r - (cash_returns.reindex(r.index).fillna(0.0) if cash_returns is not None else 0.0)
    sharpe = excess.mean() / r.std(ddof=1) * np.sqrt(periods_per_year) if r.std() > 0 else np.nan
    downside = r[r < 0].std(ddof=1) * np.sqrt(periods_per_year)
    sortino = excess.mean() * periods_per_year / downside if downside > 0 else np.nan
    mdd = max_drawdown(curve)
    return {
        "start": str(r.index[0].date()),
        "ende": str(r.index[-1].date()),
        "jahre": round(years, 1),
        "gesamtrendite": float(curve.iloc[-1] - 1),
        "cagr": float(cagr),
        "volatilitaet": float(vol),
        "sharpe": float(sharpe),
        "sortino": float(sortino),
        "max_drawdown": mdd,
        "calmar": float(cagr / abs(mdd)) if mdd < 0 else np.nan,
        "laengste_unterwasserphase_monate": longest_underwater(curve),
        "schlechtester_monat": float(r.min()),
        "schlechtestes_12m_fenster": float((1 + r).rolling(12).apply(np.prod, raw=True).min() - 1),
    }


def trade_stats(trades: pd.DataFrame) -> dict:
    """trades: DataFrame mit Spalte 'rendite' (Nettorendite je abgeschlossenem Trade)."""
    if trades is None or len(trades) < 2:
        return {"anzahl_trades": 0 if trades is None else int(len(trades))}
    r = trades["rendite"]
    wins, losses = r[r > 0], r[r <= 0]
    pf = wins.sum() / abs(losses.sum()) if losses.sum() != 0 else np.inf
    return {
        "anzahl_trades": int(len(r)),
        "gewinnquote": float((r > 0).mean()),
        "durchschn_gewinn": float(wins.mean()) if len(wins) else 0.0,
        "durchschn_verlust": float(losses.mean()) if len(losses) else 0.0,
        "profit_factor": float(pf),
        "durchschn_haltedauer_monate": float(trades["monate"].mean()),
        "max_verlustserie": _max_streak(r <= 0),
    }


def _max_streak(mask: pd.Series) -> int:
    best = run = 0
    for m in mask:
        run = run + 1 if m else 0
        best = max(best, run)
    return best
