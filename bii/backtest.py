"""Einfache, transparente Backtest-Engine für Monatsdaten.

Prinzipien:
- Gewichte werden aus Informationen bis einschließlich Monat t berechnet und erst
  `lag` Monate später wirksam (kein Look-ahead).
- Kosten: Anteil des umgeschichteten Volumens (Gebühr + halber Spread + Slippage).
- Steuern (optional): vereinfachte deutsche Abgeltungsteuer-Simulation, siehe tax_sim().
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .metrics import summarize, trade_stats

# 25 % Abgeltungsteuer + 5,5 % Soli darauf, ohne Kirchensteuer (ANNAHME)
TAX_RATE = 0.25 * 1.055


@dataclass
class BacktestResult:
    name: str
    returns: pd.Series            # Nettorendite nach Kosten, vor Steuern
    weights: pd.DataFrame         # wirksame Gewichte
    turnover: pd.Series
    costs: pd.Series
    trades: pd.DataFrame = field(default_factory=pd.DataFrame)

    def stats(self, cash: pd.Series | None = None) -> dict:
        s = summarize(self.returns, cash_returns=cash)
        s["umschichtungen_pro_jahr"] = float((self.turnover > 1e-9).sum() / max(s.get("jahre", 1), 1e-9))
        s["kosten_gesamt_pct_pa"] = float(self.costs.sum() / max(s.get("jahre", 1), 1e-9))
        s.update(trade_stats(self.trades))
        return s


def run(name: str, asset_returns: pd.DataFrame, target_weights: pd.DataFrame,
        lag: int = 2, cost_per_turnover: float = 0.002) -> BacktestResult:
    """asset_returns: Periodenrenditen je Asset (inkl. 'cash').
    target_weights: Zielgewichte zum Signalzeitpunkt (Zeilensumme 1)."""
    tw = target_weights.reindex(asset_returns.index).ffill()
    w = tw.shift(lag).dropna(how="all")
    rets = asset_returns.loc[w.index]
    # Turnover gegenüber Vorperiode (Drift innerhalb des Monats vernachlässigt, konservativ klein)
    turnover = w.diff().abs().sum(axis=1).fillna(w.abs().sum(axis=1)) / 2.0
    costs = turnover * cost_per_turnover * 2.0   # Kauf- und Verkaufsseite
    gross = (w * rets).sum(axis=1)
    net = gross - costs
    trades = _extract_trades(w, rets, cost_per_turnover)
    return BacktestResult(name, net, w, turnover, costs, trades)


def _extract_trades(w: pd.DataFrame, rets: pd.DataFrame, cost: float) -> pd.DataFrame:
    """Trades = zusammenhängende Phasen mit Gewicht > 0 in einem risikobehafteten Asset."""
    rows = []
    for col in [c for c in w.columns if c != "cash"]:
        inpos, start, acc = False, None, 1.0
        for t, wt in w[col].items():
            if wt > 1e-9:
                if not inpos:
                    inpos, start, acc = True, t, 1.0 - cost
                acc *= 1 + rets.at[t, col]
            elif inpos:
                rows.append({"asset": col, "start": start, "ende": t,
                             "monate": (t.year - start.year) * 12 + t.month - start.month,
                             "rendite": acc * (1 - cost) - 1})
                inpos = False
        if inpos:
            rows.append({"asset": col, "start": start, "ende": w.index[-1], "offen": True,
                         "monate": (w.index[-1].year - start.year) * 12 + w.index[-1].month - start.month + 1,
                         "rendite": acc * (1 - cost) - 1})
    return pd.DataFrame(rows)


def tax_sim(res: BacktestResult, price_returns: pd.DataFrame, income_returns: pd.DataFrame,
            partial_exemption: dict[str, float], start_capital: float = 10_000.0,
            liquidate_at_end: bool = True) -> dict:
    """Vereinfachte Simulation deutscher Kapitalertragsbesteuerung.

    - Realisierte Kursgewinne und laufende Erträge (Dividenden, Zinsen) werden je Kalenderjahr
      saldiert; Verluste werden vorgetragen (allgemeiner Verlusttopf, vereinfacht).
    - Teilfreistellung je Asset (Aktien-ETF: 30 %) mindert die steuerpflichtige Basis.
    - Steuer wird am Jahresende aus dem Cash/Portfolio bezahlt.
    - NICHT abgebildet: Sparer-Pauschbetrag (1.000 €), Vorabpauschale, Kirchensteuer,
      getrennter Aktienverlusttopf. -> Szenario, keine Steuerberatung.
    """
    w = res.weights
    idx = w.index
    assets = list(w.columns)
    hold = {a: 0.0 for a in assets}
    basis = {a: 0.0 for a in assets}
    total = start_capital
    taxable_year, loss_pot, taxes_paid = 0.0, 0.0, 0.0
    curve = []
    prev_w = pd.Series(0.0, index=assets)
    for i, t in enumerate(idx):
        target = w.loc[t]
        # 1) Umschichten zu Periodenbeginn (zum aktuellen Wert)
        if i == 0 or (target - prev_w).abs().sum() > 1e-9:
            for a in assets:
                tgt_val = total * target[a]
                diff = tgt_val - hold[a]
                if diff < 0 and hold[a] > 0:  # Verkauf
                    frac = -diff / hold[a]
                    gain = -diff - basis[a] * frac
                    taxable_year += gain * (1 - partial_exemption.get(a, 0.0))
                    basis[a] *= (1 - frac)
                elif diff > 0:
                    basis[a] += diff
                hold[a] = tgt_val
            cost = res.costs.loc[t] * total
            total -= cost
            scale = total / max(sum(hold.values()), 1e-12)
            for a in assets:
                hold[a] *= scale
        # 2) Wertentwicklung
        for a in assets:
            pr = price_returns.at[t, a] if a in price_returns.columns else 0.0
            inc = income_returns.at[t, a] if a in income_returns.columns else 0.0
            income = hold[a] * inc
            taxable_year += income * (1 - partial_exemption.get(a, 0.0))
            hold[a] = hold[a] * (1 + pr) + income
            basis[a] += income  # wiederangelegt
        total = sum(hold.values())
        # 3) Jahresabschluss
        is_year_end = (i == len(idx) - 1) or (idx[i + 1].year != t.year)
        if is_year_end:
            net = taxable_year - loss_pot
            if net > 0:
                tax = net * TAX_RATE
                loss_pot = 0.0
                taxes_paid += tax
                for a in assets:
                    hold[a] -= tax * hold[a] / total
                total -= tax
            else:
                loss_pot = -net
            taxable_year = 0.0
        prev_w = target
        curve.append(total)
    final_pre_liq = total
    liq_tax = 0.0
    if liquidate_at_end:
        gain = sum((hold[a] - basis[a]) * (1 - partial_exemption.get(a, 0.0)) for a in assets) - loss_pot
        liq_tax = max(gain, 0.0) * TAX_RATE
    return {
        "endwert_vor_liquidation": final_pre_liq,
        "steuern_laufend": taxes_paid,
        "steuer_bei_liquidation": liq_tax,
        "endwert_nach_steuern": final_pre_liq - liq_tax,
        "cagr_nach_steuern": ((final_pre_liq - liq_tax) / start_capital) ** (12 / len(idx)) - 1,
        "kurve": pd.Series(curve, index=idx),
    }
