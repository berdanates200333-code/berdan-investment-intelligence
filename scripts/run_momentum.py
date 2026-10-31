"""Momentum-Forschung M1–M3 gemäß docs/research/MOMENTUM_PLAN.md (vorab registriert).

Aufruf: python scripts/run_momentum.py  -> research/momentum_m1_m3.md / .json
"""
from __future__ import annotations

import itertools
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bii import backtest as bt  # noqa: E402
from bii.metrics import summarize  # noqa: E402

SNAP = ROOT / "data" / "snapshots"
OUT = ROOT / "research"
COST, COST_HI = 0.002, 0.005
IS_START, IS_END, OOS_START = "1927-01-01", "1969-12-01", "1970-01-01"
GRID = [(fam, L, S, N) for fam in ("M1", "M2", "M3") for L, S, N in itertools.product((6, 12), (0, 1), (2, 3, 5))]


def load():
    ind = pd.read_csv(SNAP / "ff_10ind_monthly.csv", index_col=0, parse_dates=True) / 100
    fac = pd.read_csv(SNAP / "ff_factors_monthly.csv", index_col=0, parse_dates=True) / 100
    idx = ind.index.intersection(fac.index)
    ind, fac = ind.loc[idx], fac.loc[idx]
    rf = fac["RF"]
    mkt = fac["Mkt-RF"] + fac["RF"]
    return ind, rf, mkt


def scores(rets: pd.DataFrame, L: int, S: int) -> pd.DataFrame:
    """Rendite über L Monate, endend S Monate vor t (nur Daten bis t)."""
    lr = np.log1p(rets)
    return np.expm1(lr.rolling(L).sum().shift(S))


def weights(fam: str, rets: pd.DataFrame, rf: pd.Series, L: int, S: int, N: int) -> pd.DataFrame:
    sc = scores(rets, L, S)
    rf_cum = np.expm1(np.log1p(rf).rolling(L).sum().shift(S))
    cols = list(rets.columns)
    rows, prev = [], []
    for t in sc.index:
        s = sc.loc[t]
        if s.isna().any() or pd.isna(rf_cum.loc[t]):
            rows.append(None); continue
        ranked = list(s.sort_values(ascending=False).index)
        ok = lambda c: fam == "M1" or s[c] > rf_cum.loc[t]  # noqa: E731
        if fam == "M3":
            rank = {c: i for i, c in enumerate(ranked)}
            hold = [c for c in prev if rank[c] < N + 2 and ok(c)][:N]
            for c in ranked:
                if len(hold) >= N:
                    break
                if c not in hold:
                    if not ok(c):
                        break
                    hold.append(c)
        else:
            hold = [c for c in ranked[:N] if ok(c)]
        prev = hold
        w = {c: (1.0 / N if c in hold else 0.0) for c in cols}
        w["cash"] = 1.0 - sum(w.values())
        rows.append(w)
    df = pd.DataFrame([r if r else {c: np.nan for c in cols + ["cash"]} for r in rows], index=sc.index)
    return df.dropna()


def run_variant(v, ind, rf, lag=1, cost=COST):
    fam, L, S, N = v
    rets = ind.assign(cash=rf)
    return bt.run(f"{fam} L{L} S{S} N{N}", rets, weights(fam, ind, rf, L, S, N), lag=lag, cost_per_turnover=cost)


def window(res, start, end=None):
    sl = slice(pd.Timestamp(start), pd.Timestamp(end) if end else None)
    t = res.trades
    if not t.empty:
        t = t[(t["start"] >= pd.Timestamp(start)) & ((t["start"] <= pd.Timestamp(end)) if end else True)]
    return bt.BacktestResult(res.name, res.returns.loc[sl], res.weights.loc[sl], res.turnover.loc[sl], res.costs.loc[sl], t)


def name(v):
    return f"{v[0]} L{v[1]} S{v[2]} N{v[3]}"


def decade_excess(r: pd.Series, mkt: pd.Series) -> list[dict]:
    out = []
    for y in range(r.index[0].year // 10 * 10, r.index[-1].year + 1, 10):
        sl = slice(pd.Timestamp(f"{y}-01-01"), pd.Timestamp(f"{y+9}-12-01"))
        a, b = r.loc[sl], mkt.loc[sl]
        if len(a) < 24:
            continue
        ca = (1 + a).prod() ** (12 / len(a)) - 1
        cb = (1 + b.loc[a.index]).prod() ** (12 / len(a)) - 1
        out.append({"jahrzehnt": f"{y}er", "strategie": ca, "markt": cb, "mehrrendite": ca - cb})
    return out


def main():
    ind, rf, mkt = load()
    res = {"erstellt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "daten": json.loads((SNAP / "manifest.json").read_text())["dateien"],
           "plan": "docs/research/MOMENTUM_PLAN.md", "anzahl_varianten": len(GRID)}
    full = {v: run_variant(v, ind, rf) for v in GRID}

    # Benchmarks
    bench_rets = pd.DataFrame({"mkt": mkt, "cash": rf})
    mkt_bh = bt.run("Markt", bench_rets, pd.DataFrame({"mkt": 1.0, "cash": 0.0}, index=mkt.index), lag=0, cost_per_turnover=COST)
    ew_w = pd.DataFrame(0.1, index=ind.index, columns=ind.columns).assign(cash=0.0)
    ew = bt.run("10 Branchen gleichgewichtet", ind.assign(cash=rf), ew_w, lag=0, cost_per_turnover=COST)

    # 1) In-Sample-Auswahl
    is_tab = {}
    for v, r in full.items():
        s = window(r, IS_START, IS_END).stats(cash=rf)
        is_tab[name(v)] = {"sharpe": s["sharpe"], "cagr": s["cagr"], "max_dd": s["max_drawdown"]}
    best = max(GRID, key=lambda v: is_tab[name(v)]["sharpe"])
    best_fam = {f: max([v for v in GRID if v[0] == f], key=lambda v: is_tab[name(v)]["sharpe"]) for f in ("M1", "M2", "M3")}
    res["in_sample_beste_variante"] = name(best)
    res["in_sample_beste_je_familie"] = {f: name(v) for f, v in best_fam.items()}

    # 2) Out-of-Sample: gewählte Varianten + Benchmarks
    oos = {}
    for label, r in [("Markt (nur halten)", mkt_bh), ("10 Branchen gleichgewichtet", ew)] + \
                    [(f"{name(v)} (IS-beste {f})", full[v]) for f, v in best_fam.items()]:
        oos[label] = window(r, OOS_START).stats(cash=rf)
    res["out_of_sample"] = oos
    all_oos = {name(v): window(r, OOS_START).stats(cash=rf) for v, r in full.items()}
    res["out_of_sample_alle_varianten"] = {k: {"cagr": s["cagr"], "sharpe": s["sharpe"], "max_dd": s["max_drawdown"],
                                              "wechsel_pa": s["umschichtungen_pro_jahr"]} for k, s in all_oos.items()}
    mkt_oos = oos["Markt (nur halten)"]
    res["anteil_varianten_cagr_ueber_markt_oos"] = float(np.mean([s["cagr"] > mkt_oos["cagr"] for s in all_oos.values()]))
    res["anteil_varianten_sharpe_ueber_markt_oos"] = float(np.mean([s["sharpe"] > mkt_oos["sharpe"] for s in all_oos.values()]))

    # 3) Walk-Forward
    pieces, choice = [], []
    for y in range(1940, ind.index[-1].year + 1, 10):
        train_end = pd.Timestamp(f"{y-1}-12-01")
        sh = {v: summarize(window(full[v], IS_START, train_end).returns, cash_returns=rf)["sharpe"] for v in GRID}
        v = max(sh, key=sh.get)
        pieces.append(full[v].returns.loc[pd.Timestamp(f"{y}-01-01"):pd.Timestamp(f"{y+9}-12-01")])
        choice.append({"fenster": f"{y}–{min(y+9, ind.index[-1].year)}", "gewaehlt": name(v)})
    wf = pd.concat(pieces)
    wf_dec = decade_excess(wf, mkt)
    res["walk_forward"] = {"auswahl": choice, "strategie": summarize(wf, cash_returns=rf),
                           "markt": summarize(mkt.loc[wf.index], cash_returns=rf), "jahrzehnte": wf_dec,
                           "anteil_jahrzehnte_positiv": float(np.mean([d["mehrrendite"] > 0 for d in wf_dec]))}

    # 4) Sensitivität für die IS-beste Variante
    sens = {}
    for lbl, lag, cost in [("Basis (lag 1, 0,2 %)", 1, COST), ("lag 2", 2, COST), ("Kosten 0,5 %", 1, COST_HI), ("lag 2 + 0,5 %", 2, COST_HI)]:
        s = window(run_variant(best, ind, rf, lag, cost), OOS_START).stats(cash=rf)
        sens[lbl] = {"cagr": s["cagr"], "mehrrendite_vs_markt": s["cagr"] - mkt_oos["cagr"], "sharpe": s["sharpe"], "max_dd": s["max_drawdown"]}
    res["sensitivitaet_beste"] = sens

    # 5) Steuer-Szenario OOS, 10.000 Start
    allr = ind.assign(mkt=mkt, cash=rf).loc[OOS_START:]
    inc = pd.DataFrame(0.0, index=allr.index, columns=allr.columns)
    inc["cash"] = allr["cash"]
    pr = allr.copy(); pr["cash"] = 0.0
    pe = {c: 0.30 for c in allr.columns if c != "cash"}
    best_oos = window(full[best], OOS_START)
    w_best = best_oos.weights.reindex(columns=allr.columns, fill_value=0.0)
    tax_best = bt.tax_sim(bt.BacktestResult("b", best_oos.returns, w_best, best_oos.turnover, best_oos.costs), pr, inc, pe)
    m_oos = window(mkt_bh, OOS_START)
    w_m = m_oos.weights.reindex(columns=allr.columns, fill_value=0.0)
    tax_m = bt.tax_sim(bt.BacktestResult("m", m_oos.returns, w_m, m_oos.turnover, m_oos.costs), pr, inc, pe)
    for t in (tax_best, tax_m):
        t.pop("kurve")
    res["steuer_szenario_oos"] = {name(best): tax_best, "Markt (nur halten)": tax_m}

    # 6) Umsetzbarkeit: US-Sektor-ETFs ab 1999 mit identischer Regel
    etf_path = SNAP / "etf_monthly.csv"
    if etf_path.exists():
        px = pd.read_csv(etf_path, index_col=0, parse_dates=True)
        sectors = [c for c in ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"] if c in px.columns]
        er = px[sectors].pct_change().dropna(how="all").dropna()
        rf_e = rf.reindex(er.index).ffill()
        spy = px["SPY"].pct_change().reindex(er.index)
        fam, L, S, N = best
        r_etf = bt.run("etf", er.assign(cash=rf_e), weights(fam, er, rf_e, L, S, N), lag=1, cost_per_turnover=COST)
        start = r_etf.returns.index[0]
        res["etf_umsetzung"] = {"zeitraum": f"{start.date()}–{er.index[-1].date()}", "regel": name(best),
                                "strategie": r_etf.stats(cash=rf_e),
                                "spy": summarize(spy.loc[start:], cash_returns=rf_e),
                                "hinweis": "kurzer Zeitraum, nur Plausibilitätsprüfung; Sektor-ETFs in USD"}
    criteria(res, mkt_oos)
    OUT.mkdir(exist_ok=True)
    (OUT / "momentum_m1_m3.json").write_text(json.dumps(res, indent=2, default=str, ensure_ascii=False))
    write_md(res)
    print((OUT / "momentum_m1_m3.md").read_text())


def criteria(res, mkt_oos):
    best = res["in_sample_beste_variante"]
    b = next(v for k, v in res["out_of_sample"].items() if k.startswith(best))
    k1 = b["cagr"] > mkt_oos["cagr"] or (b["sharpe"] > mkt_oos["sharpe"] and b["max_drawdown"] >= mkt_oos["max_drawdown"])
    k2 = res["walk_forward"]["anteil_jahrzehnte_positiv"] >= 0.6
    base = res["sensitivitaet_beste"]["Basis (lag 1, 0,2 %)"]["mehrrendite_vs_markt"]
    stress = res["sensitivitaet_beste"]["lag 2 + 0,5 %"]["mehrrendite_vs_markt"]
    k3 = base > 0 and stress >= 0.5 * base
    t = res["steuer_szenario_oos"]
    k4 = t[best]["endwert_nach_steuern"] > t["Markt (nur halten)"]["endwert_nach_steuern"]
    res["kriterien"] = {"1_oos_vorteil": bool(k1), "2_walk_forward_60pct": bool(k2), "3_robust_lag2_kosten": bool(k3),
                        "4_nach_steuern_vorn": bool(k4), "historisch_vielversprechend": bool(k1 and k2 and k3 and k4)}


def p(x):
    return "–" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x*100:.1f} %"


def write_md(r):
    def tab(d):
        rows = ["| Strategie | CAGR | Vola | Sharpe (vs. RF) | Max DD | Schlechteste 12M | Wechsel/J | Kosten p.a. |", "|---|---|---|---|---|---|---|---|"]
        for k, s in d.items():
            rows.append(f"| {k} | {p(s['cagr'])} | {p(s['volatilitaet'])} | {s['sharpe']:.2f} | {p(s['max_drawdown'])} | "
                        f"{p(s['schlechtestes_12m_fenster'])} | {s.get('umschichtungen_pro_jahr', 0):.1f} | {p(s.get('kosten_gesamt_pct_pa', 0))} |")
        return "\n".join(rows)
    wf, k = r["walk_forward"], r["kriterien"]
    allv = sorted(r["out_of_sample_alle_varianten"].items(), key=lambda kv: -kv[1]["cagr"])
    md = [
        "# Momentum M1–M3: historische Prüfung (Branchenrotation)", "",
        f"Erstellt {r['erstellt']} · Plan: [`{r['plan']}`](../{r['plan']}) (vor Datenabruf festgelegt) · {r['anzahl_varianten']} Varianten · "
        "reproduzierbar: `python scripts/run_momentum.py`", "",
        "**Status:** historisch getestet. Nicht prospektiv bewährt. Kein Einfluss auf FT1.", "",
        f"Daten: Kenneth R. French, 10 Industry Portfolios + F/F-Faktoren ({r['daten']['ff_10ind_monthly.csv']['von']} bis "
        f"{r['daten']['ff_10ind_monthly.csv']['bis']}), Monatsend-Renditen inkl. Dividenden, USD. Kosten 0,2 % je Seite, Cash = T-Bill.", "",
        "## Ergebnis nach den vorab festgelegten Kriterien",
        f"1. Out-of-Sample-Vorteil gegenüber dem Markt: **{'erfüllt' if k['1_oos_vorteil'] else 'nicht erfüllt'}**",
        f"2. Walk-Forward: Mehrrendite in mindestens 60 % der Jahrzehnte: **{'erfüllt' if k['2_walk_forward_60pct'] else 'nicht erfüllt'}** ({p(wf['anteil_jahrzehnte_positiv'])})",
        f"3. Robust bei lag 2 und 0,5 % Kosten: **{'erfüllt' if k['3_robust_lag2_kosten'] else 'nicht erfüllt'}**",
        f"4. Nach Steuern vor dem Markt: **{'erfüllt' if k['4_nach_steuern_vorn'] else 'nicht erfüllt'}**",
        f"→ **Historisch vielversprechend: {'JA' if k['historisch_vielversprechend'] else 'NEIN'}**", "",
        f"## In-Sample 1927–1969: beste Variante = **{r['in_sample_beste_variante']}**",
        "Beste je Familie: " + ", ".join(f"{f}: {v}" for f, v in r["in_sample_beste_je_familie"].items()), "",
        "## Out-of-Sample 1970–heute", tab(r["out_of_sample"]), "",
        f"Anteil aller 36 Varianten mit höherer Rendite p.a. als der Markt (OOS): {p(r['anteil_varianten_cagr_ueber_markt_oos'])}; "
        f"mit höherer Sharpe Ratio: {p(r['anteil_varianten_sharpe_ueber_markt_oos'])}", "",
        "## Sensitivität (IS-beste Variante, OOS)", "| Annahme | CAGR | Mehrrendite vs. Markt | Sharpe | Max DD |", "|---|---|---|---|---|",
        *[f"| {a} | {p(s['cagr'])} | {p(s['mehrrendite_vs_markt'])} | {s['sharpe']:.2f} | {p(s['max_dd'])} |" for a, s in r["sensitivitaet_beste"].items()], "",
        "## Walk-Forward (Auswahl nur aus Vergangenheitsdaten)", "| Fenster | gewählt |", "|---|---|",
        *[f"| {c['fenster']} | {c['gewaehlt']} |" for c in wf["auswahl"]], "",
        "| Jahrzehnt | Strategie p.a. | Markt p.a. | Mehrrendite |", "|---|---|---|---|",
        *[f"| {d['jahrzehnt']} | {p(d['strategie'])} | {p(d['markt'])} | {p(d['mehrrendite'])} |" for d in wf["jahrzehnte"]], "",
        f"Gesamt Walk-Forward: Strategie {p(wf['strategie']['cagr'])} p.a., Max DD {p(wf['strategie']['max_drawdown'])}; "
        f"Markt {p(wf['markt']['cagr'])} p.a., Max DD {p(wf['markt']['max_drawdown'])}", "",
        "## Steuer-Szenario 1970–heute (10.000 € Start, 26,375 %, Teilfreistellung 30 %)",
        "| | Endwert vor Liquidation | lfd. Steuern | Steuer bei Liquidation | Endwert netto | CAGR netto |", "|---|---|---|---|---|---|",
        *[f"| {a} | {t['endwert_vor_liquidation']:,.0f} | {t['steuern_laufend']:,.0f} | {t['steuer_bei_liquidation']:,.0f} | "
          f"{t['endwert_nach_steuern']:,.0f} | {p(t['cagr_nach_steuern'])} |" for a, t in r["steuer_szenario_oos"].items()], "",
    ]
    if "etf_umsetzung" in r:
        e = r["etf_umsetzung"]
        md += [f"## Umsetzbarkeit mit US-Sektor-ETFs ({e['zeitraum']}, Regel {e['regel']})",
               f"Strategie: CAGR {p(e['strategie']['cagr'])}, Max DD {p(e['strategie']['max_drawdown'])}, Sharpe {e['strategie']['sharpe']:.2f}, "
               f"{e['strategie']['umschichtungen_pro_jahr']:.1f} Wechsel/J  ",
               f"SPY: CAGR {p(e['spy']['cagr'])}, Max DD {p(e['spy']['max_drawdown'])}, Sharpe {e['spy']['sharpe']:.2f}  ",
               f"_{e['hinweis']}_", ""]
    md += ["## Alle 36 Varianten (OOS 1970–heute, sortiert nach Rendite p.a.)", "| Variante | CAGR | Sharpe | Max DD | Wechsel/J |", "|---|---|---|---|---|",
           *[f"| {k_} | {p(s['cagr'])} | {s['sharpe']:.2f} | {p(s['max_dd'])} | {s['wechsel_pa']:.1f} |" for k_, s in allv]]
    (OUT / "momentum_m1_m3.md").write_text("\n".join(md) + "\n")


if __name__ == "__main__":
    main()
