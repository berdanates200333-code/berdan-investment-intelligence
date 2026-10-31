"""Risikoregeln (Startannahmen laut Projektauftrag, KEINE persönliche Risikofestlegung)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskRules:
    capital: float = 10_000.0          # virtuelles Testkapital
    risk_per_trade: float = 0.0075     # max. 0,75 % Verlust je Einzeltrade (bis Stop)
    max_crypto_weight: float = 0.10
    drawdown_warning: float = 0.10     # Warnung bei -10 % vom Höchststand
    max_single_stock_weight: float = 0.10
    leverage_allowed: bool = False
    shorting_allowed: bool = False


def position_size(capital: float, entry: float, stop: float, rules: RiskRules,
                  cost_rate: float = 0.002, gap_buffer: float = 0.0) -> dict:
    """Stückzahl so, dass Verlust bis Stop (+Kosten, +optionaler Gap-Puffer) <= Risikobudget.

    gap_buffer: zusätzlicher Abschlag, weil Stops bei Kurslücken schlechter ausgeführt werden.
    """
    if stop >= entry:
        raise ValueError("Stop muss unter dem Einstieg liegen (keine Short-Positionen erlaubt)")
    budget = capital * rules.risk_per_trade
    loss_per_unit = (entry - stop) + entry * gap_buffer + entry * cost_rate * 2
    units = int(budget // loss_per_unit)
    value = units * entry
    cap = capital * rules.max_single_stock_weight
    if value > cap:
        units = int(cap // entry)
        value = units * entry
    return {"stueck": units, "positionswert": round(value, 2), "risikobudget": round(budget, 2),
            "max_verlust_bis_stop": round(units * loss_per_unit, 2),
            "gewicht": round(value / capital, 4)}


def drawdown_status(equity_history: list[float], rules: RiskRules) -> dict:
    if not equity_history:
        return {"drawdown": 0.0, "warnung": False}
    peak = max(equity_history)
    dd = equity_history[-1] / peak - 1
    return {"drawdown": dd, "hoechststand": peak, "warnung": dd <= -rules.drawdown_warning}
