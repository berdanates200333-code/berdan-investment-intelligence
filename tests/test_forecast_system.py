"""Tests: Börsenkalender, Datenqualität, gemeinsame Engine für KI-Konten, Commit-Reveal, Startschranke."""
import copy
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bii import journal  # noqa: E402
from bii.forecast import ai_portfolio as ap, calendars as cal, commitreveal as cr, gate, jr, quality  # noqa: E402
from bii.papertrading import engine  # noqa: E402

UTC = timezone.utc


def test_calendar_dst_holidays_early_close():
    assert cal.session_open("XNYS", "2026-07-01") == pd.Timestamp("2026-07-01 13:30", tz="UTC")      # Sommerzeit
    assert cal.session_open("XNYS", "2026-11-02") == pd.Timestamp("2026-11-02 14:30", tz="UTC")      # Winterzeit
    assert cal.session_close("XNYS", "2026-11-27") == pd.Timestamp("2026-11-27 18:00", tz="UTC")     # verkürzter Tag
    assert not cal.is_session("XNYS", "2026-11-26") and not cal.is_session("XETR", "2026-12-25")
    assert cal.horizon_dates("XNYS", "2026-11-02") == {"1": "2026-11-03", "5": "2026-11-09", "20": "2026-12-01"}   # Thanksgiving übersprungen
    assert cal.horizon_dates("CRYPTO", "2026-11-02")["5"] == "2026-11-07"                                        # 24/7
    assert str(cal.last_complete_session("XNYS", pd.Timestamp("2026-11-27T18:30Z")).date()) == "2026-11-25"      # 18:00 Schluss + 45 min
    assert str(cal.last_complete_session("XNYS", pd.Timestamp("2026-11-27T18:50Z")).date()) == "2026-11-27"
    assert str(cal.next_session_open("XNYS", pd.Timestamp("2026-11-25T22:00Z"))[0].date()) == "2026-11-27"


def _df(n=300, end="2026-11-02", **over):
    idx = pd.bdate_range(end=end, periods=n)
    import exchange_calendars as xc
    idx = xc.get_calendar("XNYS").sessions_in_range(idx[0], idx[-1])
    df = pd.DataFrame({"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5, "volume": 1e6}, index=idx)
    for k, v in over.items():
        df.iloc[-1, df.columns.get_loc(k)] = v
    return df


NOW = pd.Timestamp("2026-11-03T14:00Z")


def test_quality_tiers_reject_bad_data():
    ok, r = quality.check_frame(_df(), "XNYS", NOW, "USD", {"waehrung": "USD", "zeitzone": "America/New_York"})
    assert ok == quality.B and not r
    assert quality.check_frame(_df(high=50.0), "XNYS", NOW)[0] == quality.C                        # inkonsistente OHLC
    assert quality.check_frame(_df(close=float("nan")), "XNYS", NOW)[0] == quality.C               # nichtendlich
    assert quality.check_frame(_df(end="2026-10-30"), "XNYS", NOW)[0] == quality.C                 # veraltet
    assert quality.check_frame(_df(), "XNYS", NOW, "EUR", {"waehrung": "USD"})[0] == quality.C     # Währung
    assert quality.check_frame(_df(), "XNYS", NOW, "USD", {"waehrung": "USD", "zeitzone": "Europe/Berlin"})[0] == quality.C   # Handelsplatz
    gap = _df().drop(_df().index[-10])
    assert quality.check_frame(gap, "XNYS", NOW)[0] == quality.C                                   # fehlender Handelstag
    jump = _df(close=300.0, high=301.0)
    assert quality.check_frame(jump, "XNYS", NOW)[0] == quality.C                                  # Sprung > 40 %


def test_tier_a_needs_independent_confirmation():
    df = _df()
    q = quality.QualData("X", "XNYS", df, quality.B)
    d = df.index[-1]
    assert q.tier_at(d) == quality.B and not q.allowed(d, "ausfuehrung")[0] and q.allowed(d, "pilot")[0]
    q.secondary = {d: {k: float(df.loc[d, k]) for k in ("open", "high", "low", "close")}}
    assert q.tier_at(d) == quality.A and q.allowed(d, "ausfuehrung")[0]
    q.secondary[d]["close"] *= 1.05
    assert q.tier_at(d) == quality.C


# ---------------------------------------------------------------- gemeinsame Engine
class Prov:
    def __init__(self, data, tier_a=True):
        self.data, self.log = data, []
        self.tier_a = tier_a
        self.fxs = pd.Series(1.10, index=pd.date_range("2025-11-01", "2027-01-31"))

    def ohlcv(self, s):
        return self.data.get(s) if self.tier_a else None

    def fx(self):
        return self.fxs

    def crosscheck(self, *a):
        return {"status": "bestaetigt"}

    def news(self, *a):
        return {"status": "x", "treffer": [], "quellen": []}


def _market(end="2026-11-13"):
    import exchange_calendars as xc
    idx = xc.get_calendar("XNYS").sessions_in_range("2025-10-01", end)
    out = {}
    for sym, drift in (("SPY", 0.0003), ("EUNL.DE", 0.0002), ("AAPL", 0.0005)):
        c = pd.Series([100 * (1 + drift) ** i for i in range(len(idx))], index=idx)
        out[sym] = pd.DataFrame({"open": c.shift(1).fillna(c.iloc[0]), "high": c * 1.004, "low": c * 0.996, "close": c, "volume": 5e6})
    return out


def _qd(df):
    q = quality.QualData("AAPL", "XNYS", df, quality.B)
    q.secondary = {d: {k: float(df.loc[d, k]) for k in ("open", "high", "low", "close")} for d in df.index}
    q.secondary_name = "Test"
    return q


def _account(tmp_path, ki, data, now, order=True):
    rules = ap.make_rules("2026-11-02", "2027-01-31", ("AAPL",))
    st = ap.load_state(ki, rules, root=tmp_path)
    prov = Prov(data)
    ap.run_cycle(ki, st, prov, rules, now=now, root=tmp_path)           # Konto bewerten
    return rules, st, prov


def _probe_order(tmp_path, ki, rules, st, data, now):
    q = _qd(data["AAPL"])
    d = cal.last_complete_session("XNYS", now)
    c = float(data["AAPL"].loc[d, "close"])
    return ap.submit_order(ki, st, rules, "PROBELAUF:AAPL", round(c * 1.01, 2), round(c * 0.95, 2), round(c * 1.10, 2), 1.10, q, now=now, root=tmp_path, allowed={"AAPL"}, probelauf=True)


def test_both_accounts_identical_rules_separate_journals(tmp_path):
    data = _market()
    results = {}
    for ki in ("claude", "chatgpt"):
        n1 = datetime(2026, 11, 3, 22, 30, tzinfo=UTC)
        rules, st, prov = _account(tmp_path, ki, data, n1)
        e = _probe_order(tmp_path, ki, rules, st, data, n1)
        assert e["risiko_anteil"] <= 0.01 + 1e-9 and e["datum"] == "2026-11-03"
        ap.run_cycle(ki, st, prov, rules, now=datetime(2026, 11, 4, 22, 30, tzinfo=UTC), root=tmp_path)
        ap.save_state(ki, st, root=tmp_path)
        results[ki] = st
        kinds = [x["typ"] for x in journal.read(tmp_path / ki / "konto" / "handel.jsonl")]
        assert kinds.index("order_plan") < kinds.index("ausfuehrung")             # Dokumentation VOR Ausführung
        assert journal.verify(tmp_path / ki / "konto" / "handel.jsonl")[0]
    a, b = results["claude"], results["chatgpt"]
    assert a["cash_eur"] == b["cash_eur"] and a["costs_eur"] == b["costs_eur"]    # identische Regeln -> identische Ergebnisse
    assert (tmp_path / "claude" / "konto" / "handel.jsonl").read_bytes() != b""   # eigene Dateien
    assert "AAPL" in a["positions"] and a["cash_eur"] < 10_000 and a["bench"] is not None


def test_bad_data_blocks_orders_and_cycles(tmp_path):
    data = _market()
    rules = ap.make_rules("2026-11-02", "2027-01-31", ("AAPL",))
    st = ap.load_state("claude", rules, root=tmp_path)
    res = ap.run_cycle("claude", st, Prov(data, tier_a=False), rules, now=datetime(2026, 11, 3, 22, 30, tzinfo=UTC), root=tmp_path)
    assert not st["equity"] and any("Pflichtdaten" in p for p in res["probleme"])       # fail-closed
    q = quality.QualData("AAPL", "XNYS", data["AAPL"], quality.B)                        # nur Stufe B
    with pytest.raises(ValueError, match="Datenstufe"):
        ap.submit_order("claude", st, rules, "PROBELAUF:AAPL", 101, 95, 110, 1.1, q, now=datetime(2026, 11, 3, 22, 30, tzinfo=UTC), root=tmp_path, allowed={"AAPL"}, probelauf=True)


def test_orders_need_journaled_competition_forecast(tmp_path):
    rules = ap.make_rules("2026-11-02", "2027-01-31", ("AAPL",))
    st = ap.load_state("claude", rules, root=tmp_path)
    q = _qd(_market()["AAPL"])
    with pytest.raises(ValueError):
        ap.submit_order("claude", st, rules, "UNBEKANNT", 101, 95, 110, 1.1, q, now=datetime(2026, 11, 3, 22, 30, tzinfo=UTC), root=tmp_path, pj=tmp_path / "leer.jsonl")


def test_engine_has_no_fixed_open_time():
    import inspect
    src = inspect.getsource(engine)
    assert "13, 30" not in src and "21, 45" not in src


# ---------------------------------------------------------------- Commit-Reveal
P = {"prognose_id": "T-9", "instrument": {"id": "X", "name": "X", "yahoo": "X", "venue": "XNYS"}, "trade_zulaessig": False,
     "referenz": {"kurs": 100.0, "waehrung": "USD", "datum": "2026-11-02", "quelle": ["q"]},
     "horizonte": {"1": {"tage": 1, "zieltermin": "2026-11-03", "erwartung_pct": 0.5, "p_positiv": 0.6},
                   "5": {"tage": 5, "zieltermin": "2026-11-09", "erwartung_pct": 1.0, "p_positiv": 0.6},
                   "20": {"tage": 20, "zieltermin": "2026-12-01", "erwartung_pct": 2.0, "p_positiv": 0.6}},
     "entscheidung": "NICHT KAUFEN", "gruende": "g", "gegenargumente": "c", "falsifikation": "f", "quellen": ["q"], "belastbarkeit": "eingeschraenkt"}


def test_commit_reveal_protocol(tmp_path):
    prog = [copy.deepcopy(P)]
    h = cr.commitment(prog, "nonce1")
    t_commit = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)          # Öffnung 14:30, Cutoff 13:30
    cr.ingest("chatgpt", "2026-11-03", "commit", {"hash": h}, t_commit, "push", root=tmp_path)
    with pytest.raises(ValueError, match="Cutoff|Sitzung"):
        cr.ingest("claude", "2026-11-03", "commit", {"hash": h}, datetime(2026, 11, 3, 13, 45, tzinfo=UTC), "push", root=tmp_path)    # zu spät
    with pytest.raises(ValueError, match="vor Cutoff"):
        cr.ingest("chatgpt", "2026-11-03", "reveal", {"prognosen": prog, "nonce": "nonce1"}, datetime(2026, 11, 3, 13, 0, tzinfo=UTC), "push", root=tmp_path)   # zu früh
    with pytest.raises(ValueError, match="Hash"):
        cr.ingest("chatgpt", "2026-11-03", "reveal", {"prognosen": [{**prog[0], "entscheidung": "KAUFEN"}], "nonce": "nonce1"}, datetime(2026, 11, 3, 13, 40, tzinfo=UTC), "push", root=tmp_path)   # nachträglich geändert
    with pytest.raises(ValueError, match="Kein Commit"):
        cr.ingest("claude", "2026-11-03", "reveal", {"prognosen": prog, "nonce": "n"}, datetime(2026, 11, 3, 13, 40, tzinfo=UTC), "push", root=tmp_path)
    jp = tmp_path / "p.jsonl"
    r = cr.ingest("chatgpt", "2026-11-03", "reveal", {"prognosen": prog, "nonce": "nonce1"}, datetime(2026, 11, 3, 13, 40, tzinfo=UTC), "push", root=tmp_path, jpath=jp)
    assert r["prognose_ids"] == ["T-9"]
    e = journal.read(jp)[0]
    assert e["zeitnachweis"]["commit_hash"] == h and e["zeitnachweis"]["commit_utc"] < e["zeitnachweis"]["reveal_utc"]
    with pytest.raises(FileExistsError):
        cr.ingest("chatgpt", "2026-11-03", "commit", {"hash": h}, t_commit, "push", root=tmp_path)    # Belege werden nie überschrieben


# ---------------------------------------------------------------- Startschranke
def test_gate_blocks_start_and_never_backdates(tmp_path):
    g = gate.evaluate_gate(tmp_path)
    assert not g["alle_erfuellt"] and not g["bedingungen"]["automatik_chatgpt"]["ok"]
    with pytest.raises(ValueError, match="nicht erfüllt"):
        gate.start(datetime(2026, 11, 4, tzinfo=UTC), tmp_path)


def test_real_gate_not_started_and_pilot_unchanged():
    g = gate.evaluate_gate()
    assert not g["alle_erfuellt"]                                     # Wettbewerb darf heute nicht starten
    assert jr.phase() == "pilot"
    lines = [json.loads(x) for x in (ROOT / "forecast/claude/prognosen.jsonl").read_text().splitlines()]
    assert all("phase" not in e for e in lines)                       # Pilotprognosen unverändert (kein nachträgliches Feld)


def test_fx_shared_with_retry_and_failure_is_closed():
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise KeyError("rate limit")
        return pd.Series([1.1], index=[pd.Timestamp("2026-11-02")])

    prov = ap.EngineProvider(live=None, instruments={}, fx_fn=flaky)
    assert prov.fx() is not None and prov.fx() is prov.fx() and calls["n"] == 3       # 3 Versuche, danach geteilt/zwischengespeichert
    dead = ap.EngineProvider(live=None, instruments={}, fx_fn=lambda: (_ for _ in ()).throw(KeyError("x")))
    assert dead.fx() is None and dead.log                                           # fail-closed, protokolliert


# ---------------------------------------------------------------- Datenstufe A: zweck- und instrumentbezogene Grenzen
def _qa(klasse, dc, dohl=0.0, split=False, typ=None):
    df = _df()
    d = df.index[-1]
    q = quality.QualData("X", "XNYS", df, quality.B, klasse=klasse, actions={"splits": {"1": {"date": int(d.timestamp()) - 86400 * 5}}} if split else {})
    q.secondary = {d: {"open": float(df.loc[d, "open"]) * (1 + dohl), "high": float(df.loc[d, "high"]) * (1 + dohl), "low": float(df.loc[d, "low"]), "close": float(df.loc[d, "close"]) * (1 + dc)}}
    return q, d


def test_tolerances_depend_on_instrument_and_purpose():
    q, d = _qa("aktien_etf", 0.002)
    assert q.tier_at(d) == quality.A
    q, d = _qa("aktien_etf", 0.005)
    assert q.tier_at(d) == quality.C                        # 0,5 % wäre bei Aktien ok, bei ETFs nicht (Close-Grenze 0,3 %)
    q, d = _qa("aktie", 0.004)
    assert q.tier_at(d) == quality.A
    q, d = _qa("aktie", 0.0, dohl=0.012)
    assert q.tier_at(d) == quality.A                        # OHL weiter gefasst als Close
    q, d = _qa("aktie", 0.0, dohl=0.02)
    assert q.tier_at(d) == quality.C                        # früher (2 %) wäre das durchgegangen
    q, d = _qa("aktie", 0.001, split=True)
    assert q.tier_at(d) == quality.C                        # Split im Fenster: Preisdefinitionen nicht vergleichbar
    ok, r = quality.check_frame(_df(), "XNYS", NOW, "USD", {"waehrung": "USD", "zeitzone": "America/New_York", "typ": "EQUITY"}, "aktien_etf")
    assert ok == quality.C and any("Instrumententyp" in x for x in r)       # Identität: Aktie ist kein ETF


# ---------------------------------------------------------------- Benchmark in USD
def test_usd_benchmark_uses_fx_and_fees(tmp_path):
    data = _market()
    rules = ap.make_rules("2026-11-02", "2027-01-31", ("AAPL",))
    rules.BENCH = {"symbol": "EUNL.DE", "name": "USD-Test", "currency": "USD"}
    st = ap.load_state("claude", rules, root=tmp_path)
    ap.run_cycle("claude", st, Prov(data), rules, now=datetime(2026, 11, 3, 22, 30, tzinfo=UTC), root=tmp_path)
    b = st["bench"]
    assert b["waehrung"] == "USD" and b["fx_einstieg"] == 1.10
    assert abs(b["stueck"] * b["einstieg_eur"] + b["cash_eur"] + 1.0 - 10_000) < 0.05           # Kapital + 1 € Gebühr
    j = [e["typ"] for e in journal.read(tmp_path / "claude" / "konto" / "handel.jsonl")]
    assert "benchmark_ausfuehrung" in j and "tagesabschluss" in j


# ---------------------------------------------------------------- produktiver Wettbewerbszyklus (Ende-zu-Ende, mehrere Handelstage)
class FakeLive:
    def __init__(self, data):
        self.data = data

    def get(self, inst):
        return _qd(self.data[inst["yahoo"]])


def _setup_competition(tmp_path, data):
    insts = [{"id": "AAPL", "yahoo": "AAPL", "venue": "XNYS", "waehrung": "USD", "klasse": "aktie"}]
    bench = {"id": "EUNL.DE", "yahoo": "EUNL.DE", "art": "Test", "venue": "XNYS", "waehrung": "EUR", "klasse": "aktien_etf"}
    fr = tmp_path / "forecast"
    for ki in ("claude", "chatgpt"):
        (fr / ki).mkdir(parents=True)
    cfg = {"status": "gestartet", "experiment": "TEST-W", "start": "2026-11-03", "ende_exklusiv": "2027-01-02", "handelsuniversum_instrumente": insts, "benchmark_instrument": bench}
    (fr / "wettbewerb.json").write_text(json.dumps(cfg))
    # SPY wird als Kalender-/Regimeserie gebraucht
    return FakeLive({**data, "SPY": data["SPY"]})


def _forecast(ki, day):
    d = cal.last_complete_session("XNYS", pd.Timestamp(day))
    return {"prognose_id": f"{ki}-{d.date()}", "ki": ki, "phase": "wettbewerb", "entscheidung": "KAUFEN", "trade_zulaessig": True, "order": {"limit": 1000.0, "stop": 0.0, "ziel": 0.0}, "instrument": {"yahoo": "AAPL", "id": "AAPL", "venue": "XNYS"},
            "referenz": {"datum": str(d.date())}}


def test_competition_cycle_end_to_end(tmp_path):
    from bii.forecast import wettbewerb
    data = _market()
    live = _setup_competition(tmp_path, data)
    fr = tmp_path / "forecast"

    class P(Prov):
        def qual(self, sym):
            return _qd(self.data[sym])

    prov = P(data)
    prov.inst = {}
    # Nicht gestartet -> nichts passiert
    assert wettbewerb.run_daily(live, datetime(2026, 11, 3, 22, 30, tzinfo=UTC), root=tmp_path / "leer", provider=prov)["status"] == "nicht_gestartet"
    # Tag 1 (Start-Sitzung 03.11.): Benchmark-Kauf zur Eröffnung, Tagesabschluss, noch keine Orders
    r1 = wettbewerb.run_daily(live, datetime(2026, 11, 3, 22, 30, tzinfo=UTC), root=tmp_path, provider=prov)
    assert not r1["probleme"] and all(k["letzter_tag"] == "2026-11-03" for k in r1["konten"].values())
    # Beide KIs reichen vor der Folgesitzung eine Prognose mit Order ein; Order wird geplant (Journal VOR Ausführung)
    c = data["AAPL"].loc["2026-11-03", "close"]
    for ki in ("claude", "chatgpt"):
        p = _forecast(ki, "2026-11-03T22:40Z")
        p["order"] = {"limit": round(c * 1.01, 2), "stop": round(c * 0.95, 2), "ziel": round(c * 1.10, 2)}
        journal.append(p, path=fr / ki / "prognosen.jsonl", now=datetime(2026, 11, 3, 22, 35, tzinfo=UTC))
    r1b = wettbewerb.run_daily(live, datetime(2026, 11, 3, 22, 40, tzinfo=UTC), root=tmp_path, provider=prov)
    assert all(k["eingereicht"] for k in r1b["konten"].values()), r1b
    # Tag 2: Ausführung, Bewertung, Journal fortgeschrieben
    r2 = wettbewerb.run_daily(live, datetime(2026, 11, 4, 22, 30, tzinfo=UTC), root=tmp_path, provider=prov)
    assert not r2["probleme"]
    for ki in ("claude", "chatgpt"):
        ev = journal.read(fr / ki / "konto" / "handel.jsonl")
        kinds = [e["typ"] for e in ev]
        assert kinds.index("order_plan") < kinds.index("ausfuehrung") and kinds.count("tagesabschluss") == 2 and "benchmark_ausfuehrung" in kinds
        assert journal.verify(fr / ki / "konto" / "handel.jsonl")[0]
        st = json.loads((fr / ki / "konto" / "state.json").read_text())
        assert "AAPL" in st["positions"] and st["last_date"] == "2026-11-04" and len(st["equity"]) == 2
    # Tag 3: Position wird fortgeschrieben und bewertet
    r3 = wettbewerb.run_daily(live, datetime(2026, 11, 5, 22, 30, tzinfo=UTC), root=tmp_path, provider=prov)
    st = json.loads((fr / "claude" / "konto" / "state.json").read_text())
    assert st["last_date"] == "2026-11-05" and len(st["equity"]) == 3 and not r3["probleme"]


# ---------------------------------------------------------------- Startschranke: Belege statt Behauptungen
def _mk_probe(root, ki, fps, buy=True, bench_buy=True):
    from bii import journal as j
    p = root / "forecast" / "probelauf2" / ki / "konto" / "handel.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    now = datetime(2026, 11, 4, 22, 0, tzinfo=UTC)
    if buy:
        j.append({"typ": "ausfuehrung", "seite": "kauf", "ticker": "SPY"}, path=p, now=now)
    if bench_buy:
        j.append({"typ": "benchmark_ausfuehrung", "datum": "2026-11-03"}, path=p, now=now)
    for d, fp in fps.items():
        j.append({"typ": "tagesabschluss", "datum": d, "daten_fingerprint": fp}, path=p, now=now)


def test_gate_requires_executions_benchmark_same_data_and_real_days(tmp_path):
    fp = {"2026-11-03": "a", "2026-11-04": "b"}
    _mk_probe(tmp_path, "claude", fp)
    _mk_probe(tmp_path, "chatgpt", fp)
    c = gate.checks(tmp_path)
    assert c["ausfuehrungszyklus_claude"]["ok"] and c["identische_eingabedaten"]["ok"]
    assert not c["benchmark_festgeschrieben"]["ok"]                         # keine Entscheidung festgeschrieben
    _mk_probe(tmp_path / "x", "claude", fp, bench_buy=False)
    _mk_probe(tmp_path / "x", "chatgpt", fp)
    assert not gate.checks(tmp_path / "x")["ausfuehrungszyklus_claude"]["ok"]      # Kauf ohne dokumentierten Benchmark-Kauf zählt nicht
    _mk_probe(tmp_path / "y", "claude", fp)
    _mk_probe(tmp_path / "y", "chatgpt", {"2026-11-03": "a", "2026-11-04": "ANDERS"})
    assert not gate.checks(tmp_path / "y")["identische_eingabedaten"]["ok"]        # abweichende Eingabedaten
    _mk_probe(tmp_path / "z", "claude", {"2026-11-03": "a", "2026-11-07": "b"})        # 07.11. ist ein Samstag
    assert not gate.checks(tmp_path / "z")["ausfuehrungszyklus_claude"]["ok"]


def test_gate_rejects_handmade_or_same_day_automation_receipts(tmp_path):
    from bii.forecast import commitreveal as cr
    prog = [copy.deepcopy(P)]
    h = cr.commitment(prog, "n")
    jp = tmp_path / "forecast" / "chatgpt" / "prognosen.jsonl"
    jp.parent.mkdir(parents=True)
    cr.ingest("chatgpt", "2026-11-03", "commit", {"hash": h}, datetime(2026, 11, 3, 12, 0, tzinfo=UTC), "push", root=tmp_path)
    cr.ingest("chatgpt", "2026-11-03", "reveal", {"prognosen": prog, "nonce": "n"}, datetime(2026, 11, 3, 13, 40, tzinfo=UTC), "push", root=tmp_path, jpath=jp)
    c = gate.checks(tmp_path)["automatik_chatgpt"]
    assert not c["ok"] and c["detail"].startswith("0/2")          # ein Tag, keine run_id, nicht vom Bot committed -> kein Beleg


# ---------------------------------------------------------------- versiegelter Eingang
def test_sealed_submission_unreadable_until_cutoff_and_tamper_proof(tmp_path):
    from bii.forecast import sealed
    priv, pub = sealed.new_keypair()
    prog = [copy.deepcopy(P)]
    blob = sealed.encrypt(pub, prog)
    assert "NICHT KAUFEN" not in json.dumps(blob) and "T-9" not in json.dumps(blob)                       # Chiffrat verrät nichts
    priv2, _ = sealed.new_keypair()
    with pytest.raises(Exception):
        sealed.decrypt(priv2, blob)                                                                          # fremder Schlüssel (z. B. die andere KI) scheitert
    assert sealed.decrypt(priv, blob) == prog
    cr.seal_accept("chatgpt", "2026-11-03", blob, datetime(2026, 11, 3, 12, 0, tzinfo=UTC), root=tmp_path)
    with pytest.raises(ValueError, match="Cutoff"):
        cr.seal_accept("claude", "2026-11-03", blob, datetime(2026, 11, 3, 13, 45, tzinfo=UTC), root=tmp_path)    # zu spät
    tampered = {**blob, "ct": blob["ct"][:-4] + "AAAA"}
    with pytest.raises(ValueError, match="Beleg"):
        cr.seal_reveal("chatgpt", "2026-11-03", tampered, priv, datetime(2026, 11, 3, 13, 40, tzinfo=UTC), root=tmp_path)
    with pytest.raises(ValueError, match="zwischen Cutoff"):
        cr.seal_reveal("chatgpt", "2026-11-03", blob, priv, datetime(2026, 11, 3, 13, 0, tzinfo=UTC), root=tmp_path)    # vor Cutoff
    jp = tmp_path / "p.jsonl"
    r = cr.seal_reveal("chatgpt", "2026-11-03", blob, priv, datetime(2026, 11, 3, 13, 40, tzinfo=UTC), root=tmp_path, jpath=jp)
    assert r["prognose_ids"] == ["T-9"] and journal.read(jp)[0]["zeitnachweis"]["art"] == "versiegelt"
