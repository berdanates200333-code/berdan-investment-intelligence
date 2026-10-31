"""Phase-1-Strategieforschung: reproduzierbarer Backtest auf versionierten Daten.

Aufruf:  python scripts/run_backtest.py
Ergebnis: research/backtest_phase1.md und research/backtest_phase1.json
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bii import backtest as bt  # noqa: E402
from bii import strategies as st  # noqa: E402
from bii.historical import load_gold, load_sp500  # noqa: E402

COST = 0.002        # 0,2 % je Seite (Gebühr + Spread + Slippage), ANNAHME, eher konservativ
CASH_PA = 0.0       # Cash-Verzinsung 0 % (konservativ für Timing-Strategien); Sensitivität unten
OUT = ROOT / "research"


def pct(x):
    return "n/a" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x*100:,.1f} %"


def build_equity():
    sp = load_sp500()
    cash = pd.Series((1 + CASH_PA) ** (1 / 12) - 1, index=sp.index)
    rets = pd.DataFrame({"equity": sp["ret_total"], "cash": cash}).dropna()
    return sp, rets


def grid_sma(price, rets, window, lag, ns):
    rows = []
    for n in ns:
        r = bt.run(f"SMA{n}", rets.loc[window], st.sma_trend(price, n).loc[window], lag=lag, cost_per_turnover=COST)
        s = r.stats()
        rows.append({"n": n, "cagr": s["cagr"], "sharpe": s["sharpe"], "max_dd": s["max_drawdown"]})
    return pd.DataFrame(rows).set_index("n")


def walk_forward(price, rets, lag, ns, first_test=1930, step=10):
    """Auf allen Daten VOR dem Testfenster wird die beste SMA-Länge (Sharpe) gewählt
    und dann unverändert auf die nächsten `step` Jahre angewandt."""
    pieces, choices = [], []
    end_year = rets.index[-1].year
    for y in range(first_test, end_year + 1, step):
        train = slice(rets.index[0], pd.Timestamp(f"{y-1}-12-01"))
        g = grid_sma(price, rets, train, lag, ns)
        best = int(g["sharpe"].idxmax())
        test = slice(pd.Timestamp(f"{y}-01-01"), pd.Timestamp(f"{y+step-1}-12-01"))
        w = st.sma_trend(price, best)
        r = bt.run("wf", rets, w, lag=lag, cost_per_turnover=COST).returns.loc[test]
        pieces.append(r)
        choices.append({"testfenster": f"{y}-{min(y+step-1, end_year)}", "gewaehlte_sma": best})
    return pd.concat(pieces), choices


def main():
    sp, rets = build_equity()
    price = sp["price"]
    results = {"erstellt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "annahmen": {"kosten_je_seite": COST, "cash_pa": CASH_PA, "steuer": bt.TAX_RATE,
                            "datenhinweis": "Shiller-Monatsdurchschnitte; Dividenden ab 2023-07 fortgeschrieben; USD, kein FX"}}
    ns = list(range(4, 19))

    # 1) In-Sample-Kalibrierung 1881-1969, Out-of-Sample 1970-heute
    is_win = slice(pd.Timestamp("1881-01-01"), pd.Timestamp("1969-12-01"))
    oos_win = slice(pd.Timestamp("1970-01-01"), rets.index[-1])
    grids = {}
    for lag in (1, 2):
        grids[lag] = grid_sma(price, rets, is_win, lag, ns)
    best_n = int(grids[2]["sharpe"].idxmax())
    results["in_sample_beste_sma_lag2"] = best_n
    results["in_sample_grid_lag2"] = grids[2].round(4).reset_index().to_dict(orient="records")

    def compare(window, label):
        out = {}
        bh = bt.run("Buy & Hold", rets.loc[window], st.buy_hold(rets.loc[window].index, {"equity": 1.0, "cash": 0.0}), lag=0, cost_per_turnover=COST)
        out["Buy & Hold S&P 500 (TR)"] = bh
        for lag in (1, 2):
            out[f"SMA{best_n} Trendfilter (lag {lag})"] = bt.run("t", rets, st.sma_trend(price, best_n), lag=lag, cost_per_turnover=COST)
            out[f"SMA10 Standard (lag {lag})"] = bt.run("t", rets, st.sma_trend(price, 10), lag=lag, cost_per_turnover=COST)
            out[f"12M-Momentum (lag {lag})"] = bt.run("t", rets, st.abs_momentum(rets["equity"], 12), lag=lag, cost_per_turnover=COST)
        table = {}
        for k, r in out.items():
            rr = bt.BacktestResult(k, r.returns.loc[window], r.weights.loc[window], r.turnover.loc[window], r.costs.loc[window],
                                   r.trades[(r.trades["start"] >= window.start)] if not r.trades.empty else r.trades)
            table[k] = rr.stats()
        return table, out

    oos_table, oos_runs = compare(oos_win, "OOS")
    results["out_of_sample_1970_heute"] = oos_table
    is_table, _ = compare(is_win, "IS")
    results["in_sample_1881_1969"] = is_table

    # 2) Walk-forward (lag 2)
    wf_ret, wf_choices = walk_forward(price, rets, 2, ns)
    from bii.metrics import summarize
    bh_wf = rets["equity"].loc[wf_ret.index]
    results["walk_forward"] = {"auswahl": wf_choices, "strategie": summarize(wf_ret), "buy_hold": summarize(bh_wf)}

    # 3) Steuer-Szenario OOS (Aktien-ETF, Teilfreistellung 30 %), 10.000 Startkapital
    sp_o = sp.loc[oos_win]
    price_r = pd.DataFrame({"equity": sp_o["ret_price"], "cash": 0.0})
    inc_r = pd.DataFrame({"equity": sp_o["div_yield_annual"].shift(1).bfill() / 12, "cash": rets["cash"].loc[oos_win]})
    tax = {}
    for k in ["Buy & Hold S&P 500 (TR)", f"SMA{best_n} Trendfilter (lag 2)", "12M-Momentum (lag 2)"]:
        r = oos_runs[k]
        sub = bt.BacktestResult(k, r.returns.loc[oos_win], r.weights.loc[oos_win], r.turnover.loc[oos_win], r.costs.loc[oos_win])
        ts = bt.tax_sim(sub, price_r, inc_r, {"equity": 0.30})
        ts.pop("kurve")
        tax[k] = ts
    results["steuer_szenario_oos"] = tax

    # 4) Aktien + Gold ab 1972 (Gold frei handelbar seit Aug. 1971)
    gold = load_gold()
    g_win = slice(pd.Timestamp("1972-01-01"), min(rets.index[-1], gold.index[-1]))
    mret = pd.DataFrame({"equity": rets["equity"], "gold": gold.pct_change(), "cash": rets["cash"]}).dropna().loc[g_win]
    mix = {
        "100 % Aktien": st.buy_hold(mret.index, {"equity": 1.0, "gold": 0.0, "cash": 0.0}),
        "80/20 Aktien/Gold (monatl. Rebal.)": st.buy_hold(mret.index, {"equity": 0.8, "gold": 0.2, "cash": 0.0}),
    }
    gp = gold.reindex(price.index).dropna()
    mix["Trend-Tranchen 80/20 (SMA10, lag 2)"] = st.sleeves_trend({"equity": price.loc[gp.index], "gold": gp}, 10, {"equity": 0.8, "gold": 0.2})
    results["aktien_gold_1972_heute"] = {}
    for k, w in mix.items():
        lag = 2 if "Trend" in k else 0
        r = bt.run(k, mret, w, lag=lag, cost_per_turnover=COST)
        r = bt.BacktestResult(k, r.returns.loc[g_win], r.weights.loc[g_win], r.turnover.loc[g_win], r.costs.loc[g_win], r.trades)
        results["aktien_gold_1972_heute"][k] = r.stats()

    # 5) Sensitivität Cash-Zins 3 % p.a. (für Trendfilter relevant)
    cash3 = pd.Series(1.03 ** (1 / 12) - 1, index=rets.index)
    rets3 = rets.assign(cash=cash3)
    r3 = bt.run("t", rets3, st.sma_trend(price, best_n), lag=2, cost_per_turnover=COST)
    results["sensitivitaet_cash3pct_oos"] = bt.BacktestResult("x", r3.returns.loc[oos_win], r3.weights.loc[oos_win], r3.turnover.loc[oos_win], r3.costs.loc[oos_win]).stats()

    OUT.mkdir(exist_ok=True)
    (OUT / "backtest_phase1.json").write_text(json.dumps(results, indent=2, default=str, ensure_ascii=False))
    write_md(results, best_n)
    print((OUT / "backtest_phase1.md").read_text())


def table_md(d: dict) -> str:
    cols = [("cagr", "CAGR"), ("volatilitaet", "Vola"), ("sharpe", "Sharpe*"), ("max_drawdown", "Max DD"),
            ("schlechtestes_12m_fenster", "Schlechteste 12M"), ("laengste_unterwasserphase_monate", "Unterwasser (M)"),
            ("umschichtungen_pro_jahr", "Wechsel/J"), ("gewinnquote", "Trefferquote"), ("profit_factor", "Profit F.")]
    lines = ["| Strategie | " + " | ".join(c[1] for c in cols) + " |", "|---" * (len(cols) + 1) + "|"]
    for name, s in d.items():
        vals = []
        for key, _ in cols:
            v = s.get(key)
            if key in ("sharpe", "profit_factor", "umschichtungen_pro_jahr"):
                vals.append("–" if v is None else f"{v:.2f}")
            elif key == "laengste_unterwasserphase_monate":
                vals.append(str(v))
            else:
                vals.append(pct(v) if v is not None else "–")
        lines.append(f"| {name} | " + " | ".join(vals) + " |")
    return "\n".join(lines)


def write_md(r: dict, best_n: int):
    wf = r["walk_forward"]
    md = [
        "# Backtest Phase 1 – Trendfilter vs. Buy & Hold (S&P 500, Monatsdaten)",
        "",
        f"Erstellt: {r['erstellt']} · reproduzierbar mit `python scripts/run_backtest.py`",
        "",
        "**Status nach Projektdefinition:** technisch funktionierend, *historisch getestet*. Nicht prospektiv bewährt.",
        "",
        "## Annahmen",
        f"- Kosten: {COST*100:.1f} % je Kauf/Verkauf (Gebühr + Spread + Slippage).",
        f"- Cash-Verzinsung: {CASH_PA*100:.0f} % (konservativ; Sensitivität mit 3 % unten).",
        "- Daten: Shiller S&P 500 (Monats**durchschnitte**), Dividenden ab 2023-07 fortgeschrieben, USD, ohne Währungseffekt EUR.",
        "- lag 1 = Signal aus Monat t, gehandelt ab t+1 (optimistisch wegen Durchschnittskursen); lag 2 = konservativ.",
        "- *Sharpe hier ohne Abzug eines risikofreien Zinses (Cash = 0 %).",
        "",
        f"## In-Sample-Kalibrierung 1881–1969 → beste SMA-Länge (lag 2): **{best_n} Monate**",
        "",
        "## Out-of-Sample 1970–heute (nicht zur Kalibrierung genutzt)",
        table_md(r["out_of_sample_1970_heute"]),
        "",
        "## In-Sample 1881–1969 (zum Vergleich)",
        table_md(r["in_sample_1881_1969"]),
        "",
        "## Walk-Forward (SMA-Länge jeweils nur aus Vergangenheit gewählt, lag 2)",
        "| Fenster | gewählte SMA |", "|---|---|",
        *[f"| {c['testfenster']} | {c['gewaehlte_sma']} |" for c in wf["auswahl"]],
        "",
        f"Walk-Forward Strategie: CAGR {pct(wf['strategie']['cagr'])}, Max DD {pct(wf['strategie']['max_drawdown'])}, Vola {pct(wf['strategie']['volatilitaet'])}  ",
        f"Buy & Hold gleicher Zeitraum: CAGR {pct(wf['buy_hold']['cagr'])}, Max DD {pct(wf['buy_hold']['max_drawdown'])}, Vola {pct(wf['buy_hold']['volatilitaet'])}",
        "",
        "## Steuer-Szenario 1970–heute, 10.000 Startkapital (Aktien-ETF, Teilfreistellung 30 %, 26,375 %)",
        "| Strategie | Endwert vor Liq. | lfd. Steuern | Steuer bei Liq. | Endwert netto | CAGR netto |", "|---|---|---|---|---|---|",
        *[f"| {k} | {v['endwert_vor_liquidation']:,.0f} | {v['steuern_laufend']:,.0f} | {v['steuer_bei_liquidation']:,.0f} | {v['endwert_nach_steuern']:,.0f} | {pct(v['cagr_nach_steuern'])} |"
          for k, v in r["steuer_szenario_oos"].items()],
        "",
        "## Aktien + Gold 1972–heute",
        table_md(r["aktien_gold_1972_heute"]),
        "",
        f"## Sensitivität: SMA{best_n} lag 2 mit 3 % Cash-Zins (OOS)",
        f"CAGR {pct(r['sensitivitaet_cash3pct_oos']['cagr'])}, Max DD {pct(r['sensitivitaet_cash3pct_oos']['max_drawdown'])}",
    ]
    (OUT / "backtest_phase1.md").write_text("\n".join(md) + "\n")


if __name__ == "__main__":
    main()
