"""Regelwerke, die Zielgewichte aus historisch bekannten Daten erzeugen.

Jede Funktion bekommt nur Daten bis zum jeweiligen Zeitpunkt t (rollierende Fenster);
die Verzögerung bis zur Ausführung setzt backtest.run(lag=...) um.
"""
from __future__ import annotations

import pandas as pd


def buy_hold(index: pd.Index, weights: dict[str, float]) -> pd.DataFrame:
    return pd.DataFrame({k: v for k, v in weights.items()}, index=index)


def sma_trend(price: pd.Series, n: int, asset: str = "equity") -> pd.DataFrame:
    """Regel T1: Investiert, wenn Kurs > gleitender Durchschnitt der letzten n Monate, sonst Cash."""
    sma = price.rolling(n).mean()
    on = (price > sma).astype(float).where(sma.notna())
    return pd.DataFrame({asset: on, "cash": 1 - on}).dropna()


def abs_momentum(total_ret: pd.Series, n: int, cash_ret: pd.Series | None = None,
                 asset: str = "equity") -> pd.DataFrame:
    """Regel T2: Investiert, wenn n-Monats-Gesamtrendite > Cash-Rendite im selben Zeitraum."""
    mom = (1 + total_ret).rolling(n).apply(lambda x: x.prod(), raw=True) - 1
    hurdle = 0.0 if cash_ret is None else (1 + cash_ret).rolling(n).apply(lambda x: x.prod(), raw=True) - 1
    on = (mom > hurdle).astype(float).where(mom.notna())
    return pd.DataFrame({asset: on, "cash": 1 - on}).dropna()


def sleeves_trend(prices: dict[str, pd.Series], n: int, sleeve_weights: dict[str, float]) -> pd.DataFrame:
    """Regel T3: Mehrere Anlageklassen mit festem Budget; jede Tranche unabhängig per SMA-Filter.
    Nicht investierte Tranchen liegen in Cash."""
    parts = {}
    for a, p in prices.items():
        sma = p.rolling(n).mean()
        parts[a] = ((p > sma).astype(float) * sleeve_weights[a]).where(sma.notna())
    df = pd.DataFrame(parts).dropna()
    df["cash"] = 1 - df.sum(axis=1)
    return df
