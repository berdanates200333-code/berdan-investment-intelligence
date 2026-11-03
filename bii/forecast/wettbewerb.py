"""Produktiver Wettbewerbszyklus: verarbeitet NACH dem Start täglich die ECHTEN KI-Konten (forecast/<ki>/konto) über die gemeinsame Engine.

Ablauf je Lauf (nach US-Börsenschluss):
  1. Engine-Zyklus je Konto: Orders der Vorsitzung ausführen, Exits, Bewertung, Benchmark, Pause, Tagesabschluss mit Daten-Prüfsumme.
  2. Neue KAUFEN-Prognosen mit trade_zulaessig und order{limit,stop,ziel} werden als dokumentierte Orders eingereicht (Ausführung frühestens nächste Sitzung).
  3. Prüfung: beide Konten müssen für jeden Tag dieselbe Daten-Prüfsumme haben, sonst Fehler.
Solange wettbewerb.json nicht 'gestartet' ist, passiert nichts (keine Konten, kein Rückdatieren).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .. import journal
from . import ai_portfolio as ap, calendars, jr, universe

ROOT = Path(__file__).resolve().parents[2]


def load_config(root: Path = ROOT):
    f = root / "forecast" / "wettbewerb.json"
    try:
        c = json.loads(f.read_text())
    except (OSError, ValueError):
        return None
    return c if c.get("status") == "gestartet" else None


def pending_orders(ki: str, forecast_root: Path, info_date: str | None = None, source: str | None = None, offensiv: bool = False):
    """KAUFEN-Prognosen der Wettbewerbsphase ohne Orderplan/-ablehnung. Nur Prognosen für den aktuellen Informationsstichtag (info_date) – veraltete
    Prognosen werden nie nachträglich geordert. Hauptkonto handelt keine 'nur_offensiv'-Prognosen; das Offensivkonto (offensiv=True) handelt alle."""
    done = {e.get("prognose_id") for e in journal.read(forecast_root / ki / "konto" / "handel.jsonl") if e["typ"] in ("order_plan", "order_abgelehnt")}
    for p in journal.read(forecast_root / (source or ki) / "prognosen.jsonl"):
        if p.get("phase") != "wettbewerb" or p["entscheidung"] != "KAUFEN" or not p.get("trade_zulaessig") or p["prognose_id"] in done:
            continue
        if info_date and p["referenz"]["datum"] != info_date:
            continue
        if p.get("nur_offensiv") and not offensiv:
            continue
        yield p


def _setup(live, now, root, provider, cfg):
    insts = {i["yahoo"]: i for i in cfg["handelsuniversum_instrumente"] + [cfg["benchmark_instrument"]]}
    prov = provider or ap.EngineProvider(live, insts)             # EIN Anbieter für alle Konten
    bench = {"symbol": cfg["benchmark_instrument"]["yahoo"], "name": cfg["benchmark_instrument"]["art"], "currency": cfg["benchmark_instrument"]["waehrung"]}
    return insts, prov, bench


def _rules_today(cfg, bench, prov, st):
    """Handelbar ist heute nur, was Datenstufe A hat (Rest wird ausgelassen, nicht der ganze Tag abgebrochen). Gehaltene/geplante Titel MÜSSEN Daten haben."""
    syms = [i["yahoo"] for i in cfg["handelsuniversum_instrumente"]]
    avail = {x for x in syms if prov.ohlcv(x) is not None}
    needed = set(st["positions"]) | {o["ticker"] for o in st["pending"]}
    missing = sorted(needed - avail)
    rules = ap.make_rules(cfg["start"], cfg["ende_exklusiv"], tuple(sorted(avail | needed)), version=cfg["experiment"])
    rules.BENCH = bench
    return rules, missing, sorted(set(syms) - avail)


def run_daily(live, now: datetime | None = None, root: Path = ROOT, provider=None, submit: bool = True) -> dict:
    """Nächtlicher Zyklus (submit=False im Workflow): Engine-Zyklus je Konto. Orders werden vor der Eröffnung durch submit_orders_only eingereicht."""
    now = now or datetime.now(timezone.utc)
    cfg = load_config(root)
    if cfg is None:
        return {"status": "nicht_gestartet", "konten": {}}
    fr = root / "forecast"
    kis = tuple(cfg.get("kis", jr.KIS))
    insts, prov, bench = _setup(live, now, root, provider, cfg)
    out = {"status": "gestartet", "modus": cfg.get("modus", "duell"), "konten": {}, "probleme": []}
    for ki in kis:
        st = ap.load_state(ki, ap.make_rules(cfg["start"], cfg["ende_exklusiv"], (), version=cfg["experiment"]), root=fr)
        rules, missing, skipped = _rules_today(cfg, bench, prov, st)
        if missing:
            out["probleme"].append(f"{ki}: Daten fehlen für gehaltene/geplante Titel {missing} – kein Zyklus")
            continue
        res = ap.run_cycle(ki, st, prov, rules, now=now, root=fr)
        out["probleme"] += [f"{ki}: {x}" for x in res["probleme"]]
        ap.save_state(ki, st, root=fr)
        out["konten"][ki] = {"verarbeitet": res["verarbeitet"], "positionen": list(st["positions"]), "letzter_tag": st["last_date"], "ausgelassen_heute": skipped,
                             "aktiv_eur": st["equity"][-1]["aktiv_eur"] if st["equity"] else None}
    if submit:
        so = submit_orders_only(live, now, root, prov)
        for ki, v in so["konten"].items():
            out["konten"].setdefault(ki, {}).update(v)
        out["probleme"] += so["probleme"]
    if len(kis) > 1:
        fps = {ki: {e["datum"]: e["daten_fingerprint"] for e in journal.read(fr / ki / "konto" / "handel.jsonl") if e["typ"] == "tagesabschluss"} for ki in kis}
        common = set(fps[kis[0]]) & set(fps[kis[1]])
        diff = sorted(d for d in common if fps[kis[0]][d] != fps[kis[1]][d])
        if diff or set(fps[kis[0]]) != set(fps[kis[1]]):
            out["probleme"].append(f"Kontenprüfung: Daten-Prüfsummen weichen ab/Tage fehlen ({diff or 'unterschiedliche Tage'})")
    return out


def submit_orders_only(live, now: datetime | None = None, root: Path = ROOT, provider=None) -> dict:
    """Vor der Eröffnung (Workflow ~12:30 UTC): neue KAUFEN-Prognosen mit order{limit,stop,ziel} als dokumentierte Orders einreichen.
    Informationsstichtag = letzter abgeschlossener Handelstag; Ausführung frühestens zur nächsten Eröffnung (Nachtlauf)."""
    now = now or datetime.now(timezone.utc)
    cfg = load_config(root)
    out = {"konten": {}, "probleme": []}
    if cfg is None:
        return out
    fr = root / "forecast"
    insts, prov, bench = _setup(live, now, root, provider, cfg)
    for ki in tuple(cfg.get("kis", jr.KIS)):
        st = ap.load_state(ki, ap.make_rules(cfg["start"], cfg["ende_exklusiv"], (), version=cfg["experiment"]), root=fr)
        rules, missing, _ = _rules_today(cfg, bench, prov, st)
        submitted, rejected = [], []
        if now < __import__("pandas").Timestamp(cfg["ende_exklusiv"]).tz_localize("UTC") and pd_ge(now, cfg["start"], 0):
            for p in pending_orders(ki, fr, str(calendars.last_complete_session('XNYS', now).date())):
                try:
                    fx = prov.fx()
                    q = live.get(p["instrument"]) if live is not None else prov.qual(p["instrument"]["yahoo"])
                    o = p["order"]
                    e = ap.submit_order(ki, st, rules, p["prognose_id"], o["limit"], o["stop"], o["ziel"], float(fx.iloc[-1]), q, now=now, root=fr,
                                        allowed=set(rules.UNIVERSE), pj=fr / ki / "prognosen.jsonl")
                    submitted.append(e["id"])
                except Exception as ex:  # noqa: BLE001 - abgelehnte Order wird dokumentiert, kein Systemfehler
                    rejected.append({"prognose_id": p["prognose_id"], "grund": str(ex)})
                    journal.append({"typ": "order_abgelehnt", "ki": ki, "prognose_id": p["prognose_id"], "grund": str(ex), "version": rules.VERSION}, path=fr / ki / "konto" / "handel.jsonl", now=now)
        ap.save_state(ki, st, root=fr)
        out["konten"][ki] = {"eingereicht": submitted, "abgelehnt": rejected}
    return out


def pd_ge(now, start: str, hours: int) -> bool:
    """Orders erst ab dem Start-Handelstag (Vorlauf: Einreichung am Morgen des Starttags ist erlaubt)."""
    import pandas as pd
    return pd.Timestamp(now).tz_convert("UTC") >= pd.Timestamp(start).tz_localize("UTC") - pd.Timedelta(hours=hours)
