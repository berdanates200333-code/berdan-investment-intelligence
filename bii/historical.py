"""Laden und Validieren der historischen Datensätze (versioniert im Repo).

Quellen (öffentlich, über GitHub 'datasets' gespiegelt):
- S&P 500 monatlich ab 1871 (Robert Shiller, Yale): github.com/datasets/s-and-p-500
- Gold monatlich ab 1833: github.com/datasets/gold-prices

Wichtige, dokumentierte Einschränkungen:
1. Shiller-Kurse sind MONATSDURCHSCHNITTE, keine Schlusskurse. Durchschnitte erzeugen
   künstliche Autokorrelation (Working-Effekt) und lassen Trendfolge besser aussehen.
   -> Backtests nutzen standardmäßig eine Ausführungsverzögerung von 2 Monaten.
2. Dividenden enden im Datensatz 2023-06. Danach wird die letzte bekannte
   Dividendenrendite (12-Monats-Mittel) fortgeschrieben -> ANNAHME.
3. Der S&P 500 ist ein US-Index in USD. Ein deutscher Anleger trägt zusätzlich
   EUR/USD-Währungsrisiko, das hier NICHT abgebildet ist.
4. Kein Survivorship-Bias auf Indexebene im klassischen Sinn (Index = ganzes Universum),
   aber der US-Markt war rückblickend einer der erfolgreichsten der Welt (Erfolgsbias des Landes).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
HIST = ROOT / "data" / "historical"


def load_sp500() -> pd.DataFrame:
    d = pd.read_csv(HIST / "sp500_shiller_monthly.csv", parse_dates=["Date"]).set_index("Date")
    d = d[d["SP500"] > 0].copy()
    price = d["SP500"]
    div = d["Dividend"].replace(0.0, np.nan)
    div_yield = (div / price)
    last_known = div_yield.last_valid_index()
    fill_value = div_yield.loc[:last_known].tail(12).mean()
    div_yield = div_yield.copy()
    div_yield.loc[div_yield.index > last_known] = fill_value
    div_yield = div_yield.ffill()
    out = pd.DataFrame({
        "price": price,
        "div_yield_annual": div_yield,
        "long_rate": d["Long Interest Rate"].replace(0.0, np.nan).ffill() / 100.0,
    })
    out["div_assumed"] = out.index > last_known
    out["ret_price"] = out["price"].pct_change()
    out["ret_total"] = out["ret_price"] + out["div_yield_annual"].shift(1) / 12.0
    _validate(out["price"], "S&P 500")
    return out


def load_gold() -> pd.Series:
    g = pd.read_csv(HIST / "gold_monthly.csv")
    g["Date"] = pd.to_datetime(g["Date"] + "-01")
    s = g.set_index("Date")["Price"].astype(float)
    _validate(s, "Gold")
    return s


def _validate(s: pd.Series, name: str) -> None:
    if s.index.has_duplicates:
        raise ValueError(f"{name}: doppelte Zeitstempel")
    if not s.index.is_monotonic_increasing:
        raise ValueError(f"{name}: Zeitreihe nicht sortiert")
    if (s <= 0).any():
        raise ValueError(f"{name}: nicht-positive Kurse")
    jumps = s.pct_change().abs()
    if (jumps > 0.6).any():
        raise ValueError(f"{name}: unplausibler Monatssprung > 60 % bei {jumps.idxmax().date()}")
