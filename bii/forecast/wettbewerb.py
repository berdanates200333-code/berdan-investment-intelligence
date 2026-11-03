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


def pending_orders(ki: str, forecast_root: Path):
    """KAUFEN-Prognosen der Wettbewerbsphase ohne Orderplan."""
    done = {e.get("prognose_id") for e in journal.read(forecast_root / ki / "konto" / "handel.jsonl") if e["typ"] == "order_plan"}
    for p in journal.read(forecast_root / ki / "prognosen.jsonl"):
        if p.get("phase") == "wettbewerb" and p["entscheidung"] == "KAUFEN" and p.get("trade_zulaessig") and p["prognose_id"] not in done:
            yield p


def run_daily(live, now: datetime | None = None, root: Path = ROOT, provider=None) -> dict:
    now = now or datetime.now(timezone.utc)
    cfg = load_config(root)
    if cfg is None:
        return {"status": "nicht_gestartet", "konten": {}}
    fr = root / "forecast"
    insts = {i["yahoo"]: i for i in cfg["handelsuniversum_instrumente"] + [cfg["benchmark_instrument"]]}
    rules = ap.make_rules(cfg["start"], cfg["ende_exklusiv"], tuple(i["yahoo"] for i in cfg["handelsuniversum_instrumente"]), version=cfg["experiment"])
    rules.BENCH = {"symbol": cfg["benchmark_instrument"]["yahoo"], "name": cfg["benchmark_instrument"]["art"], "currency": cfg["benchmark_instrument"]["waehrung"]}
    prov = provider or ap.EngineProvider(live, insts)             # EIN Anbieter für beide Konten
    out = {"status": "gestartet", "konten": {}, "probleme": []}
    states = {}
    for ki in jr.KIS:
        st = ap.load_state(ki, rules, root=fr)
        res = ap.run_cycle(ki, st, prov, rules, now=now, root=fr)
        out["probleme"] += [f"{ki}: {x}" for x in res["probleme"]]
        submitted = []
        if not res["probleme"] and now < __import__("pandas").Timestamp(cfg["ende_exklusiv"]).tz_localize("UTC"):
            for p in pending_orders(ki, fr):
                q = live.get(p["instrument"]) if live is not None else None
                try:
                    fx = prov.fx()
                    o = p["order"]
                    e = ap.submit_order(ki, st, rules, p["prognose_id"], o["limit"], o["stop"], o["ziel"], float(fx.iloc[-1]), q or prov.qual(p["instrument"]["yahoo"]),
                                        now=now, root=fr, allowed=set(rules.UNIVERSE), pj=fr / ki / "prognosen.jsonl")
                    submitted.append(e["id"])
                except Exception as ex:  # noqa: BLE001 - abgelehnte Order wird dokumentiert, kein Systemfehler
                    out["konten"].setdefault(ki, {}).setdefault("abgelehnt", []).append({"prognose_id": p["prognose_id"], "grund": str(ex)})
                    journal.append({"typ": "order_abgelehnt", "ki": ki, "prognose_id": p["prognose_id"], "grund": str(ex), "version": rules.VERSION}, path=fr / ki / "konto" / "handel.jsonl", now=now)
        ap.save_state(ki, st, root=fr)
        states[ki] = st
        out["konten"].setdefault(ki, {}).update(verarbeitet=res["verarbeitet"], eingereicht=submitted, positionen=list(st["positions"]), letzter_tag=st["last_date"],
                                                aktiv_eur=st["equity"][-1]["aktiv_eur"] if st["equity"] else None)
    fps = {ki: {e["datum"]: e["daten_fingerprint"] for e in journal.read(fr / ki / "konto" / "handel.jsonl") if e["typ"] == "tagesabschluss"} for ki in jr.KIS}
    common = set(fps["claude"]) & set(fps["chatgpt"])
    diff = sorted(d for d in common if fps["claude"][d] != fps["chatgpt"][d])
    if diff or set(fps["claude"]) != set(fps["chatgpt"]):
        out["probleme"].append(f"Kontenprüfung: Daten-Prüfsummen weichen ab/Tage fehlen ({diff or 'unterschiedliche Tage'})")
    return out
