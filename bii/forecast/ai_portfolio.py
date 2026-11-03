"""Virtuelle KI-Konten auf der GEMEINSAMEN Engine (bii.papertrading.engine) – keine zweite Handelslogik.

Beide KIs: identische Regeln (rules_v1_0.PARAMS: Gebühren, Spread, Slippage, Währung, Risiko 1 %, max. 5 Positionen, Drawdown-Pause),
identische Kursversorgung (qualitätsgeprüft, nur Stufe A), identischer Ausführungscode. Getrennt sind nur Konto, Zustand und Journal:
  forecast/<ki>/konto/state.json, forecast/<ki>/konto/handel.jsonl
Die KI liefert Prognose-ID, Limit-/Stop-/Zielkurs; die Positionsgröße bestimmt die gemeinsame Risikoregel (engine.size_position).
Eigene Signalplanung der Engine ist abgeschaltet (evaluate liefert nie einen Kandidaten).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from .. import journal
from ..papertrading import engine, rules_v1_0 as base_rules
from ..papertrading.data import ecb_eurusd
from . import calendars, jr, quality, universe

ROOT = Path(__file__).resolve().parents[2]
FORECAST = ROOT / "forecast"          # Wurzel der KI-Konten: <wurzel>/<ki>/konto/{state.json,handel.jsonl}


def make_rules(start: str, end: str, tradable: tuple, version: str = "FC1-1.0") -> SimpleNamespace:
    ns = SimpleNamespace(**{k: v for k, v in vars(base_rules).items() if not k.startswith("__")})
    ns.VERSION, ns.START, ns.END, ns.UNIVERSE = version, start, end, tuple(tradable)
    ns.evaluate = lambda *a, **k: {"ok": False, "gruende": ["Signalplanung deaktiviert (KI liefert Orders)"], "kennzahlen": {}, "score": 0.0}
    return ns


class EngineProvider:
    """Adapter Live-Daten -> Engine-Schnittstelle. Daten unterhalb Stufe A werden NICHT geliefert (fail-closed)."""

    def __init__(self, live, instruments: dict, fx_fn=ecb_eurusd):
        self.live, self.inst, self._fx_fn, self.log = live, instruments, fx_fn, []

    def ohlcv(self, sym):
        q = self.live.get(self.inst[sym]) if sym in self.inst else None
        if q is None:
            self.log.append(f"{sym}: keine Daten")
            return None
        t = q.tier_at(q.df.index[-1])
        if quality.RANK[t] < quality.RANK[quality.A]:
            self.log.append(f"{sym}: Datenstufe {t} unzulässig für Ausführung ({'; '.join(q.reasons) or 'keine Zweitquelle'})")
            return None
        return q.df

    def fx(self):
        """EUR/USD einmal je Lauf laden (3 Versuche) und für ALLE Konten teilen – gleiche Kursversorgung für beide KIs."""
        if getattr(self, "_fx", None) is not None:
            return self._fx
        for _ in range(3):
            try:
                self._fx = self._fx_fn()
                if self._fx is not None and len(self._fx):
                    return self._fx
            except Exception as e:  # noqa: BLE001
                self.log.append(f"EUR/USD: {type(e).__name__}")
        self._fx = None
        return None

    def crosscheck(self, sym, d, close, tol):
        q = self.live.get(self.inst[sym])
        return {"status": "bestaetigt" if q and q.tier_at(d) == quality.A else "ungeprueft", "quelle": getattr(q, "secondary_name", None)}

    def news(self, sym, days, neg):
        return {"status": "nicht_genutzt", "treffer": [], "quellen": []}


def account_dir(ki: str, root: Path = FORECAST) -> Path:
    d = root / ki / "konto"
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_state(ki: str, rules, root: Path = FORECAST) -> dict:
    p = account_dir(ki, root) / "state.json"
    return json.loads(p.read_text()) if p.exists() else engine.new_state(rules)


def save_state(ki: str, state: dict, root: Path = FORECAST) -> None:
    (account_dir(ki, root) / "state.json").write_text(json.dumps(state, indent=1, ensure_ascii=False, sort_keys=True))


def submit_order(ki: str, state: dict, rules, prognose_id: str, limit: float, stop: float, target: float, fx_usd_per_eur: float, qd: quality.QualData,
                 now: datetime | None = None, root: Path = FORECAST, allowed: set | None = None, pj: Path | None = None, probelauf: bool = False) -> dict:
    """Nimmt eine Kauf-Order der KI an (nur nach journalisierter KAUFEN-Prognose), dokumentiert sie VOR der Ausführung im Kontojournal."""
    now = now or datetime.now(timezone.utc)
    if probelauf:      # Systemprobelauf: synthetische Prognose, identischer Orderpfad, strikt getrennt vom Wettbewerb
        prog = {"entscheidung": "KAUFEN", "trade_zulaessig": True, "phase": "probelauf", "erstellt_utc": "1970-01-01T00:00:00+00:00",
                "instrument": {"yahoo": prognose_id.split(":")[1], "id": prognose_id.split(":")[1], "venue": "XNYS"}}
    else:
        prog = next((p for p in journal.read(pj or jr.path(ki)) if p["prognose_id"] == prognose_id), None)
        if prog is None or prog["entscheidung"] != "KAUFEN" or not prog.get("trade_zulaessig"):
            raise ValueError("Order nur zu einer journalisierten KAUFEN-Prognose mit trade_zulaessig=true")
        if prog.get("phase") != "wettbewerb":
            raise ValueError("Orders nur in der Wettbewerbsphase (Pilotprognosen werden nicht gehandelt)")
    t = prog["instrument"]["yahoo"]
    if t not in rules.UNIVERSE or (allowed is not None and t not in allowed):
        raise ValueError(f"{t} ist nicht im zugelassenen Handelsuniversum")
    venue = calendars.venue_of(prog["instrument"])
    info = calendars.last_complete_session(venue, now)
    ok, tier = qd.allowed(info, "ausfuehrung")
    if not ok:
        raise ValueError(f"Datenstufe {tier} unzulässig für virtuelle Ausführung")
    if prog["erstellt_utc"] >= now.isoformat(timespec="seconds"):
        raise ValueError("Prognose muss vor der Order journalisiert sein")
    if t in state["positions"] or any(o["ticker"] == t for o in state["pending"]):
        raise ValueError("Position/Order bereits vorhanden")
    entry = float(qd.df.loc[info, "close"])
    if not (0.01 * entry <= entry - stop <= 0.15 * entry) or target <= entry or limit < entry:
        raise ValueError("Stop/Ziel/Limit unplausibel (Stop 1–15 % unter Kurs, Ziel über Kurs, Limit >= Kurs)")
    if len(state["positions"]) + len(state["pending"]) >= rules.PARAMS["max_positions"]:
        raise ValueError("Positionslimit erreicht")
    equity = state["equity"][-1]["aktiv_eur"] if state["equity"] else state["kapital_eur"]
    reserved = sum(o["max_kosten_eur"] for o in state["pending"])
    sz = engine.size_position(equity, entry, limit, stop, fx_usd_per_eur, state["cash_eur"] - reserved, rules)
    if sz["stueck"] < 1:
        raise ValueError(sz["grund"])
    oid = f"{rules.VERSION}-{ki.upper()}-{t}-{info.date()}"
    e = journal.append({"typ": "order_plan", "id": oid, "ki": ki, "version": rules.VERSION, "ticker": t, "datum": str(info.date()), "prognose_id": prognose_id, "probelauf": probelauf,
                        "orderart": "Kauf Limit (nächste Sitzung), Stop-Market, Kursziel-Limit, Zeitstopp", "einstieg": entry, "limit": limit, "stop": stop, "ziel": target,
                        "stueck": sz["stueck"], "positionswert_eur": sz["positionswert_eur"], "risikogrenze_eur": sz["max_verlust_eur"],
                        "risiko_anteil": round(sz["max_verlust_eur"] / equity, 4), "datenstufe": tier, "zweitquelle": qd.secondary_name},
                       path=account_dir(ki, root) / "handel.jsonl", now=now)
    state["pending"].append({"id": oid, "ticker": t, "plan_datum": str(info.date()), "journal_utc": e["erstellt_utc"], "limit": limit, "stop": stop, "ziel": target,
                             "stueck": sz["stueck"], "grund_kurz": f"KI-Prognose {prognose_id}", "max_kosten_eur": sz["positionswert_eur"] * 1.01 + rules.PARAMS["fee_eur"]})
    return e


def run_cycle(ki: str, state: dict, provider, rules, now: datetime | None = None, root: Path = FORECAST, freigaben=None) -> dict:
    """Ein Ausführungszyklus über die gemeinsame Engine (Orders ausführen, Exits, Bewertung, Pause, Benchmark)."""
    return engine.run(state, provider, rules, account_dir(ki, root) / "handel.jsonl", now=now, vetos=[], freigaben=freigaben or [])
