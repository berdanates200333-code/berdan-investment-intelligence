"""Paper-Trading-Engine: Orderplanung, simulierte Ausführung, Risikoregeln, Journal, Benchmark.

Ablauf je neuem, vollständig abgeschlossenem Handelstag d (in Reihenfolge):
  1. Gültige Orders aus der Vorperiode werden zu den Kursen von d simuliert (Eröffnungskurs, Limit, Kosten,
     mögliche Ablehnung). Eine Order gilt nur, wenn ihr Journaleintrag VOR der Eröffnung von d erstellt wurde.
  2. Exits (Stop / Ziel / Zeitstopp) für offene Positionen werden mit den Tagesbalken von d simuliert.
  3. Bewertung zum Schlusskurs, Drawdown-Prüfung, Pause.
  4. Nur für den NEUESTEN Tag: neue Orderpläne werden zuerst ins Journal geschrieben, dann vorgemerkt.
Alle Entscheidungen nutzen nur Daten bis einschließlich d. Konto: EUR; Handel: USD (mit Währungsumrechnung).
"""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from .. import journal
from ..forecast import calendars

# Handelszeiten kommen aus dem Börsenkalender (XNYS: Sommerzeit, Feiertage, verkürzte Tage) – keine feste UTC-Uhrzeit mehr.
def _close_ready(d) -> datetime:
    """Zeitpunkt, ab dem der Tagesbalken von d endgültig ist (Handelsschluss + 45 min)."""
    return (calendars.session_close("XNYS", d) + calendars.BAR_SETTLE).to_pydatetime()


def _open_utc(d) -> datetime:
    return calendars.session_open("XNYS", d).to_pydatetime()


def new_state(rules) -> dict:
    return {"version": rules.VERSION, "start": rules.START, "kapital_eur": rules.CAPITAL_EUR, "last_date": None,
            "cash_eur": rules.CAPITAL_EUR, "positions": {}, "pending": [], "closed": [], "failed": [], "equity": [],
            "peak": rules.CAPITAL_EUR, "paused": False, "pause_seit": None, "bench": None, "costs_eur": 0.0,
            "daten_log": [], "plaene_verworfen": []}


def _ts(d, hm) -> datetime:
    return datetime(d.year, d.month, d.day, hm[0], hm[1], tzinfo=timezone.utc)


def _fx_before(fx: pd.Series, d) -> float:
    s = fx[fx.index < pd.Timestamp(d)]
    if s.empty:
        raise ValueError("Kein zum Entscheidungszeitpunkt verfügbarer Wechselkurs")
    value = float(s.iloc[-1])
    if not math.isfinite(value) or value <= 0:
        raise ValueError("Ungültiger Wechselkurs")
    return value


def _fx_upto(fx: pd.Series, d) -> float:
    s = fx[fx.index <= pd.Timestamp(d)]
    if s.empty:
        raise ValueError("Kein zum Entscheidungszeitpunkt verfügbarer Wechselkurs")
    value = float(s.iloc[-1])
    if not math.isfinite(value) or value <= 0:
        raise ValueError("Ungültiger Wechselkurs")
    return value


def _rejected(order_id: str, rate: float) -> bool:
    return int(hashlib.sha256(order_id.encode()).hexdigest(), 16) % 10_000 < rate * 10_000


def _jw(path: Path, entry: dict, late: bool, now: datetime) -> dict:
    if late:
        entry = {**entry, "nachtraeglich_verarbeitet": True}
    return journal.append(entry, path=path, now=now)


def equity_eur(state: dict, closes: dict, fx: float) -> float:
    return state["cash_eur"] + sum(p["stueck"] * closes.get(t, p["letzter_kurs"]) / fx for t, p in state["positions"].items())


# ---------------------------------------------------------------- Ausführung
def _execute_entry(state, o, bar, fx, rules, d, jpath, late, now):
    P = rules.PARAMS
    base = {"typ": "ausfuehrung_fehlgeschlagen", "plan_id": o["id"], "ticker": o["ticker"], "datum": str(d.date()), "version": rules.VERSION}
    reason = None
    if bar is None:
        reason = "Kein Kursbalken am Ausführungstag"
    elif _rejected(o["id"], P["reject_rate"]):
        reason = "Simulierte Ablehnung/Störung bei der Ausführung"
    elif bar["open"] > o["limit"]:
        reason = f"Eröffnung {bar['open']:.2f} über Kauflimit {o['limit']:.2f} (Gap) – nicht ausgeführt"
    elif bar["open"] <= o["stop"]:
        reason = f"Eröffnung {bar['open']:.2f} bereits unter Stop {o['stop']:.2f} – nicht ausgeführt"
    if reason is None:
        fill = min(o["limit"], bar["open"] * (1 + P["half_spread"] + P["slippage"]))
        usd = o["stueck"] * fill
        eur = usd / fx * (1 + P["fx_fee"]) + P["fee_eur"]
        if eur > state["cash_eur"] or len(state["positions"]) >= P["max_positions"] or o["ticker"] in state["positions"]:
            reason = "Barmittel/Positionslimit reicht nicht (kein Hebel, keine Kredite)"
    if reason:
        state["failed"].append({"plan_id": o["id"], "datum": str(d.date()), "ticker": o["ticker"], "grund": reason})
        _jw(jpath, {**base, "grund": reason}, late, now)
        return
    cost = eur - usd / fx
    state["cash_eur"] -= eur
    state["costs_eur"] += cost
    state["positions"][o["ticker"]] = {
        "plan_id": o["id"], "ticker": o["ticker"], "stueck": o["stueck"], "einstieg": round(fill, 4), "einstieg_datum": str(d.date()),
        "stop": o["stop"], "stop_start": o["stop"], "ziel": o["ziel"], "risiko_je_stueck": round(fill - o["stop"], 4),
        "fx_einstieg": fx, "einstieg_eur": round(eur, 2), "kosten_eur": round(cost, 2), "tage": 0, "exit_zeitstopp": False,
        "letzter_kurs": float(bar["close"]), "grund": o["grund_kurz"]}
    _jw(jpath, {"typ": "ausfuehrung", "seite": "kauf", "plan_id": o["id"], "ticker": o["ticker"], "datum": str(d.date()), "version": rules.VERSION,
                "kurs_usd": round(fill, 4), "stueck": o["stueck"], "kosten_eur": round(cost, 2), "fx": fx}, late, now)


def _close_position(state, t, fill, d, fx, reason, rules, jpath, late, now, target=False):
    P = rules.PARAMS
    p = state["positions"].pop(t)
    usd = p["stueck"] * fill
    eur = usd / fx * (1 - P["fx_fee"]) - P["fee_eur"]
    cost = usd / fx * P["fx_fee"] + P["fee_eur"]
    state["cash_eur"] += eur
    state["costs_eur"] += cost
    pnl = eur - p["einstieg_eur"]
    r = (fill - p["einstieg"]) / p["risiko_je_stueck"] if p["risiko_je_stueck"] else 0.0
    tr = {"plan_id": p["plan_id"], "ticker": t, "einstieg_datum": p["einstieg_datum"], "ausstieg_datum": str(d.date()),
          "einstieg_usd": p["einstieg"], "ausstieg_usd": round(fill, 4), "stueck": p["stueck"], "pnl_eur": round(pnl, 2),
          "kosten_eur": round(p["kosten_eur"] + cost, 2), "r_multiple": round(r, 2), "tage": p["tage"], "grund": reason, "einstiegsgrund": p["grund"]}
    state["closed"].append(tr)
    _jw(jpath, {"typ": "ausfuehrung", "seite": "verkauf", "plan_id": p["plan_id"], "ticker": t, "datum": str(d.date()), "version": rules.VERSION,
                "kurs_usd": round(fill, 4), "stueck": p["stueck"], "grund": reason, "pnl_eur": tr["pnl_eur"], "fx": fx}, late, now)


def _process_exits(state, bars, fx, rules, d, jpath, late, now):
    P = rules.PARAMS
    for t in list(state["positions"]):
        p, b = state["positions"][t], bars.get(t)
        if b is None:
            continue
        slip = 1 - P["half_spread"] - P["slippage"]
        if p["exit_zeitstopp"]:
            _close_position(state, t, b["open"] * slip, d, fx, f"Zeitstopp ({P['max_hold_days']} Handelstage) – Verkauf zur Eröffnung", rules, jpath, late, now)
        elif b["open"] <= p["stop"]:
            _close_position(state, t, b["open"] * slip, d, fx, "Stop (Kurslücke: Ausführung zur Eröffnung)", rules, jpath, late, now)
        elif b["low"] <= p["stop"]:
            _close_position(state, t, p["stop"] * slip, d, fx, "Stop erreicht", rules, jpath, late, now)
        elif b["high"] >= p["ziel"]:
            _close_position(state, t, max(p["ziel"], b["open"]), d, fx, "Kursziel erreicht (Limit-Verkauf)", rules, jpath, late, now)


def _end_of_day_updates(state, bars, rules, d, jpath, late, now):
    P = rules.PARAMS
    for t, p in state["positions"].items():
        b = bars.get(t)
        if b is None:
            continue
        p["letzter_kurs"] = float(b["close"])
        p["tage"] += 1
        if b["close"] >= p["einstieg"] + P["breakeven_r"] * p["risiko_je_stueck"] and p["stop"] < p["einstieg"]:
            old, p["stop"] = p["stop"], round(p["einstieg"], 4)
            _jw(jpath, {"typ": "order_update", "ticker": t, "plan_id": p["plan_id"], "datum": str(d.date()), "version": rules.VERSION,
                        "aenderung": "Stop auf Einstand (Break-even) nach +1R", "stop_alt": old, "stop_neu": p["stop"], "gilt_ab": "nächster Handelstag"}, late, now)
        if p["tage"] >= P["max_hold_days"] and not p["exit_zeitstopp"]:
            p["exit_zeitstopp"] = True
            _jw(jpath, {"typ": "exit_plan", "ticker": t, "plan_id": p["plan_id"], "datum": str(d.date()), "version": rules.VERSION,
                        "orderart": "Verkauf zum Markt (Eröffnung)", "grund": f"Zeitstopp nach {P['max_hold_days']} Handelstagen", "gilt_ab": "nächster Handelstag"}, late, now)


# ---------------------------------------------------------------- Planung
def size_position(equity: float, entry: float, limit: float, stop: float, fx: float, cash_free: float, rules) -> dict:
    """Stückzahl so, dass der Verlust bis Stop (inkl. Spread, Slippage, Währungs- und Fixkosten, gerechnet ab Kauflimit)
    höchstens risk_per_trade des Portfolios beträgt. Kein Hebel: Kosten <= freie Barmittel."""
    P = rules.PARAMS
    budget = equity * P["risk_per_trade"] - 2 * P["fee_eur"]
    per_share_usd = (limit - stop) + limit * 2 * (P["half_spread"] + P["slippage"])
    per_share_eur = per_share_usd / fx + (limit / fx) * 2 * P["fx_fee"]
    if budget <= 0 or per_share_eur <= 0:
        return {"stueck": 0, "grund": "Risikobudget zu klein"}
    n = math.floor(budget / per_share_eur)
    max_w = math.floor(equity * P["max_position_weight"] * fx / limit)
    max_cash = math.floor(max(cash_free - P["fee_eur"], 0) * fx / (limit * (1 + P["half_spread"] + P["slippage"]) * (1 + P["fx_fee"])))
    n = min(n, max_w, max_cash)
    value_eur = n * limit / fx
    if n < 1 or value_eur < P["min_position_eur"]:
        return {"stueck": 0, "grund": f"Positionsgröße {value_eur:.0f} € unter Mindestgröße / Limit"}
    return {"stueck": n, "positionswert_eur": round(value_eur, 2), "max_verlust_eur": round(n * per_share_eur + 2 * P["fee_eur"], 2)}


def _plan_entries(state, bars_hist, spy, fx, rules, d, jpath, provider, vetos, now, late):
    P = rules.PARAMS
    if state["paused"]:
        state["plaene_verworfen"].append({"datum": str(d.date()), "grund": "Pause für neue Positionen (Drawdown-Grenze)"})
        return
    ok, reg = rules.regime_ok(spy, d)
    if not ok:
        state["plaene_verworfen"].append({"datum": str(d.date()), "grund": "Marktfilter: SPY unter SMA100", "daten": reg})
        return
    held = set(state["positions"]) | {o["ticker"] for o in state["pending"]}
    slots = P["max_positions"] - len(held)
    cands = []
    for t, df in bars_hist.items():
        if df is None or t in held:
            continue
        ev = rules.evaluate(df, spy, d)
        if ev["ok"]:
            cands.append((ev["score"], t, ev))
    cands.sort(reverse=True)
    equity = state["equity"][-1]["aktiv_eur"] if state["equity"] else state["kapital_eur"]
    reserved = sum(o["max_kosten_eur"] for o in state["pending"])
    new = 0
    for score, t, ev in cands:
        if new >= min(slots, P["max_new_per_day"]):
            break
        skip = None
        veto = [v for v in vetos if v["ticker"] == t and v.get("gueltig_bis", "9999") >= str(d.date())]
        if veto:
            skip = f"Claude-Veto: {veto[-1]['grund']}"
        cc = provider.crosscheck(t, d, ev["kennzahlen"]["schluss"], P["crosscheck_tol"])
        if not skip and cc["status"] != "bestaetigt":
            skip = f"Datenqualität: Zweitquelle nicht bestätigt ({cc['status']})"
        nw = provider.news(t, P["news_days"], rules.NEG_NEWS)
        if not skip and nw["treffer"]:
            skip = f"Nachrichten-Veto: {nw['treffer'][0][:100]}"
        entry, atr = ev["kennzahlen"]["schluss"], ev["atr"]
        stop = round(entry - P["stop_atr"] * atr, 2)
        limit = round(entry * (1 + P["limit_gap"]), 2)
        target = round(entry + P["target_r"] * (entry - stop), 2)
        sz = size_position(equity, entry, limit, stop, fx, state["cash_eur"] - reserved, rules)
        if not skip and sz["stueck"] < 1:
            skip = sz["grund"]
        if skip:
            state["plaene_verworfen"].append({"datum": str(d.date()), "ticker": t, "grund": skip})
            _jw(jpath, {"typ": "plan_verworfen", "ticker": t, "datum": str(d.date()), "version": rules.VERSION, "grund": skip, "kennzahlen": ev["kennzahlen"]}, late, now)
            continue
        oid = f"PT{rules.VERSION}-{t}-{d.date()}"
        grund = "Trend + Ausbruch über 20-Tage-Hoch mit Volumen, relative Stärke ggü. SPY, Marktfilter intakt"
        e = _jw(jpath, {
            "typ": "order_plan", "id": oid, "version": rules.VERSION, "ticker": t, "datum": str(d.date()), "datenstand": f"Tagesschluss {d.date()}",
            "orderart": "Kauf Limit (gültig für den nächsten Handelstag), danach Stop-Market + Kursziel-Limit + Zeitstopp",
            "entscheidungsgrundlage": grund, "regelergebnisse": ev["gruende"], "kennzahlen": ev["kennzahlen"], "marktfilter": reg,
            "einstieg": entry, "limit": limit, "stop": stop, "ziel": target, "zeitstopp_tage": P["max_hold_days"],
            "stueck": sz["stueck"], "positionswert_eur": sz["positionswert_eur"], "risikogrenze_eur": sz["max_verlust_eur"],
            "risiko_anteil": round(sz["max_verlust_eur"] / equity, 4), "datenpruefung": cc, "nachrichtenpruefung": {k: v for k, v in nw.items() if k != "treffer"} | {"treffer": nw["treffer"]},
            "quellen": ["Yahoo Finance (Tagesbalken)", cc.get("quelle", "Stooq (nicht verfügbar)"), "Google News RSS"] + (nw.get("quellen") or []),
        }, late, now)
        state["pending"].append({"id": oid, "ticker": t, "plan_datum": str(d.date()), "journal_utc": e["erstellt_utc"], "limit": limit, "stop": stop, "ziel": target,
                                 "stueck": sz["stueck"], "grund_kurz": grund, "max_kosten_eur": sz["positionswert_eur"] * 1.01 + P["fee_eur"]})
        reserved += sz["positionswert_eur"] * 1.01 + P["fee_eur"]
        new += 1


# ---------------------------------------------------------------- Hauptlauf
def _bench_buy(state, df, rules, d, fx=1.0):
    """Benchmark-Kauf zur Eröffnung. EUR-Benchmark direkt; USD-Benchmark mit EZB-Vortageskurs und Währungsgebühr (wie die Aktienkonten)."""
    P = rules.PARAMS
    b = df.loc[pd.Timestamp(d)]
    cur = rules.BENCH.get("currency", "EUR")
    fill_local = b["open"] * (1 + P["half_spread"] + P["slippage"])
    fill = fill_local if cur == "EUR" else fill_local / fx * (1 + P["fx_fee"])        # EUR je Stück inkl. Währungsgebühr
    n = math.floor((state["kapital_eur"] - P["fee_eur"]) / fill)
    cost = P["fee_eur"] + n * (fill - b["open"] / (1 if cur == "EUR" else fx))
    state["bench"] = {"symbol": rules.BENCH["symbol"], "waehrung": cur, "stueck": n, "einstieg_eur": round(fill, 4), "datum": str(d.date()), "fx_einstieg": fx,
                      "cash_eur": round(state["kapital_eur"] - n * fill - P["fee_eur"], 2), "kosten_eur": round(cost, 2)}


def _bench_value(state, bench_df, rules, d, fx_val):
    be = state["bench"]
    px = float(bench_df.loc[d, "close"])
    return be["stueck"] * (px if be.get("waehrung", "EUR") == "EUR" else px / fx_val) + be["cash_eur"]


def _fingerprint(universe, spy, bench_df, rules, d, fx_before, fx_upto) -> str:
    """Prüfsumme ALLER Eingabedaten eines Handelstags (Balken, Benchmark, Kurse): beide KI-Konten müssen dieselbe Prüfsumme haben."""
    rows = {}
    for sym, df in [*sorted(universe.items()), (rules.REGIME, spy), (rules.BENCH["symbol"], bench_df)]:
        rows[sym] = [round(float(df.loc[d, k]), 6) for k in ("open", "high", "low", "close", "volume")] if df is not None and d in df.index else None
    return hashlib.sha256(json.dumps({"bars": rows, "fx_vortag": round(fx_before, 8), "fx_tag": round(fx_upto, 8)}, sort_keys=True).encode()).hexdigest()


def run(state: dict, provider, rules, jpath: Path, now: datetime | None = None, vetos: list | None = None, freigaben: list | None = None, ende: str | None = None) -> dict:
    """Verarbeitet alle neuen, abgeschlossenen Handelstage. Rückgabe: Zusammenfassung des Laufs."""
    now = now or datetime.now(timezone.utc)
    vetos, freigaben = vetos or [], freigaben or []
    summary = {"verarbeitet": [], "probleme": []}
    valid, message = journal.verify(jpath)
    if not valid:
        summary["probleme"] = ["Journalintegrität: " + message]
        return summary
    ende = pd.Timestamp(ende or rules.END)
    spy = provider.ohlcv(rules.REGIME)
    bench_df = provider.ohlcv(rules.BENCH["symbol"])
    fx = provider.fx()
    if spy is None or fx is None or bench_df is None:
        summary["probleme"] = list(provider.log) + ["Pflichtdaten (SPY/Benchmark/EUR-USD) fehlen – kein Handel, nur Protokoll"]
        state["daten_log"].append({"zeit": now.isoformat(timespec="seconds"), "probleme": summary["probleme"]})
        return summary
    universe = {t: provider.ohlcv(t) for t in rules.UNIVERSE}
    days = [d for d in spy.index if d >= pd.Timestamp(rules.START) and now >= _close_ready(d)
            and (state["last_date"] is None or d > pd.Timestamp(state["last_date"]))]
    # Fail closed before any execution or valuation. Never trade on a partial universe.
    problems = list(provider.log)
    if any(df is None or df.empty for df in universe.values()):
        problems.append("Universum unvollständig – keine Ausführung")
    if spy.empty or bench_df.empty or fx.empty:
        problems.append("Leere Pflichtdaten")
    if not spy.empty:
        completed = spy.index[spy.index <= pd.Timestamp(now.date())]
        if len(completed) == 0 or (pd.Timestamp(now.date()) - completed[-1]).days > 4:
            problems.append("SPY veraltet oder ohne historischen Balken")
    for day in days:
        try:
            _fx_before(fx, day)
            _fx_upto(fx, day)
        except ValueError as exc:
            problems.append(str(exc))
        if any(df is None or day not in df.index for df in universe.values()):
            problems.append(f"Universum ohne vollständige Balken für {day.date()}")
    if problems:
        summary["probleme"] = problems
        state["daten_log"].append({"zeit": now.isoformat(timespec="seconds"), "probleme": problems})
        return summary
    last_day = days[-1] if days else None
    for d in days:
        late = d != last_day
        bars = {t: (df.loc[d] if df is not None and d in df.index else None) for t, df in universe.items()}
        fxe = _fx_before(fx, d)
        # Pause freigeben (nur durch dokumentierte manuelle Freigabe nach Pausenbeginn)
        if state["paused"] and any(f["datum"] > state["pause_seit"] and f["datum"] <= str(d.date()) for f in freigaben):
            state["paused"] = False
            state["peak"] = state["equity"][-1]["aktiv_eur"]
            _jw(jpath, {"typ": "pause_beendet", "datum": str(d.date()), "version": rules.VERSION, "grund": "manuelle Freigabe (papertrading/freigabe.json)"}, late, now)
        if state["bench"] is None and d in bench_df.index:
            _bench_buy(state, bench_df, rules, d, fxe)
            _jw(jpath, {"typ": "benchmark_ausfuehrung", "datum": str(d.date()), "version": rules.VERSION, **{k: v for k, v in state["bench"].items()}}, late, now)
        # 1. Orders ausführen
        for o in list(state["pending"]):
            if pd.Timestamp(o["plan_datum"]) >= d:
                continue
            state["pending"].remove(o)
            if o["journal_utc"] >= _open_utc(d).isoformat(timespec="seconds"):
                state["failed"].append({"plan_id": o["id"], "datum": str(d.date()), "ticker": o["ticker"], "grund": "Plan erst nach Handelseröffnung dokumentiert – verworfen"})
                _jw(jpath, {"typ": "ausfuehrung_fehlgeschlagen", "plan_id": o["id"], "ticker": o["ticker"], "datum": str(d.date()), "version": rules.VERSION,
                            "grund": "Plan erst nach Handelseröffnung dokumentiert – verworfen"}, late, now)
                continue
            _execute_entry(state, o, bars.get(o["ticker"]), fxe, rules, d, jpath, late, now)
        # 2. Exits
        _process_exits(state, bars, fxe, rules, d, jpath, late, now)
        # 3. Bewertung
        _end_of_day_updates(state, bars, rules, d, jpath, late, now)
        closes = {t: float(b["close"]) for t, b in bars.items() if b is not None}
        eq = equity_eur(state, closes, _fx_upto(fx, d))
        be = state["bench"]
        bench_eq = _bench_value(state, bench_df, rules, d, _fx_upto(fx, d)) if be and d in bench_df.index else (state["equity"][-1]["bench_eur"] if state["equity"] else state["kapital_eur"])
        dq = [x for x in provider.log if not x.startswith("Hinweis")]
        state["peak"] = max(state["peak"], eq)
        state["equity"].append({"datum": str(d.date()), "aktiv_eur": round(eq, 2), "bench_eur": round(bench_eq, 2), "cash_eur": round(state["cash_eur"], 2),
                                "positionen": len(state["positions"]), "daten_ok": not dq})
        _jw(jpath, {"typ": "tagesabschluss", "datum": str(d.date()), "version": rules.VERSION, "aktiv_eur": round(eq, 2), "bench_eur": round(bench_eq, 2),
                    "daten_fingerprint": _fingerprint(universe, spy, bench_df, rules, d, fxe, _fx_upto(fx, d))}, late, now)
        if not state["paused"] and eq / state["peak"] - 1 <= -rules.PARAMS["drawdown_pause"]:
            state["paused"], state["pause_seit"] = True, str(d.date())
            _jw(jpath, {"typ": "pause", "datum": str(d.date()), "version": rules.VERSION, "grund": f"Portfoliorückgang {eq/state['peak']-1:.1%} vom Höchststand – keine neuen Positionen",
                        "aktiv_eur": round(eq, 2), "hoechststand_eur": round(state["peak"], 2)}, late, now)
        # 4. Planung (nur neuester Tag)
        if not late and d <= ende:
            hist = {t: df for t, df in universe.items()}
            _plan_entries(state, hist, spy, _fx_upto(fx, d), rules, d, jpath, provider, vetos, now, late)
        state["last_date"] = str(d.date())
        summary["verarbeitet"].append(str(d.date()))
    state["daten_log"].append({"zeit": now.isoformat(timespec="seconds"), "tage": summary["verarbeitet"], "probleme": list(provider.log)})
    state["daten_log"] = state["daten_log"][-60:]
    summary["probleme"] = list(provider.log)
    return summary
