"""Performance-Portfolio (offensive Risikostufe) – getrenntes virtuelles Konto 'claude_offensiv' auf der GEMEINSAMEN Engine.

Gleiche Daten, Kosten, Währungsregeln, Ausführungslogik und Claudes Prognosen wie das Hauptkonto; unterschiedlich NUR die vorab festgelegten Risikoparameter
(Größeneffekt). Prognosen mit `nur_offensiv: true` (risikoreichere Chancen) handelt nur dieses Konto und werden getrennt ausgewertet (Auswahleffekt).
Das Hauptkonto (forecast/claude/konto) und seine Automatik werden hier nicht berührt.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .. import journal
from . import ai_portfolio as ap, calendars, wettbewerb

ROOT = Path(__file__).resolve().parents[2]
KI = "claude_offensiv"
SOURCE = "claude"          # Prognosequelle (read-only)
PARAMETER = {"risk_per_trade": 0.02, "max_open_risk": 0.06, "max_position_weight": 0.30, "drawdown_pause": 0.15, "max_positions": 5}


def cfg_path(root: Path = ROOT) -> Path:
    return root / "forecast" / "offensiv" / "config.json"


def load_config(root: Path = ROOT):
    try:
        c = json.loads(cfg_path(root).read_text())
    except (OSError, ValueError):
        return None
    return c if c.get("status") == "gestartet" else None


def init(now: datetime, root: Path = ROOT) -> dict:
    """Konfiguration und Konto festschreiben. Start = Start des Hauptkontos, nur wenn dieser noch in der Zukunft liegt (kein Rückdatieren)."""
    main = wettbewerb.load_config(root)
    if main is None:
        raise ValueError("Hauptkonto nicht gestartet")
    day, opening = calendars.next_session_open("XNYS", now)
    if str(day.date()) > main["start"] or opening.isoformat() != main["start_eroeffnung_utc"]:
        raise ValueError(f"Start {main['start']} liegt nicht mehr in der Zukunft oder weicht ab; Offensivkonto würde zu spät beginnen")
    if cfg_path(root).exists():
        raise ValueError("Offensivkonfiguration existiert bereits (wird nie überschrieben)")
    cfg = {"status": "gestartet", "modus": "offensiv", "experiment": "FC1-OFFENSIV-1", "konto": KI, "prognosequelle": SOURCE, "kapital_eur": 10000,
           "start": main["start"], "start_eroeffnung_utc": main["start_eroeffnung_utc"], "ende_exklusiv": main["ende_exklusiv"], "letzter_kalendertag": main["letzter_kalendertag"],
           "festgeschrieben_utc": now.isoformat(timespec="seconds"), "parameter": PARAMETER,
           "handelsuniversum_instrumente": main["handelsuniversum_instrumente"], "benchmark_instrument": main["benchmark_instrument"],
           "ziele_nach_kosten_60t_pct": {"interessant": 3, "stark": 5, "ausserordentlich": 10},
           "regel": "Getrenntes Risikoprofil. Zielmarken sind experimentell, kein Versprechen. Stopkurse sind KEINE garantierte Verlustgrenze: Kurslücken werden zu Marktpreisen gefüllt (Engine)."}
    cfg_path(root).parent.mkdir(parents=True, exist_ok=True)
    cfg_path(root).write_text(json.dumps(cfg, indent=1, ensure_ascii=False))
    rules = ap.make_rules(cfg["start"], cfg["ende_exklusiv"], (), version=cfg["experiment"])
    fr = root / "forecast"
    ap.save_state(KI, ap.load_state(KI, rules, root=fr), root=fr)
    journal.append({"typ": "konto_eroeffnet", "ki": KI, "kapital_eur": 10000, "start": cfg["start"], "parameter": PARAMETER, "version": cfg["experiment"]},
                   path=ap.account_dir(KI, fr) / "handel.jsonl", now=now)
    return cfg


def _rules(cfg, prov, st):
    insts, _, bench = wettbewerb._setup(None, None, None, prov, cfg)
    rules, missing, skipped = wettbewerb._rules_today(cfg, bench, prov, st)
    rules.PARAMS = {**rules.PARAMS, **cfg["parameter"]}          # NEUES Dict: das gemeinsame PARAMS-Objekt des Hauptkontos bleibt unverändert
    return rules, missing, skipped


def run_cycle(live, now=None, root: Path = ROOT, provider=None) -> dict:
    now = now or datetime.now(timezone.utc)
    cfg = load_config(root)
    if cfg is None:
        return {"status": "nicht_gestartet"}
    fr = root / "forecast"
    prov = provider or ap.EngineProvider(live, {i["yahoo"]: i for i in cfg["handelsuniversum_instrumente"] + [cfg["benchmark_instrument"]]})
    st = ap.load_state(KI, ap.make_rules(cfg["start"], cfg["ende_exklusiv"], (), version=cfg["experiment"]), root=fr)
    rules, missing, skipped = _rules(cfg, prov, st)
    out = {"status": "gestartet", "probleme": []}
    if missing:
        out["probleme"].append(f"Daten fehlen für gehaltene/geplante Titel {missing} – kein Zyklus")
        return out
    res = ap.run_cycle(KI, st, prov, rules, now=now, root=fr)
    out["probleme"] += res["probleme"]
    ap.save_state(KI, st, root=fr)
    if st["paused"]:                         # Pause -> vollständige Risikoanalyse einmalig dokumentieren
        from . import lab
        rp = root / "reports" / "forecast" / f"risikoanalyse_{KI}_{st['pause_seit']}.md"
        if not rp.exists():
            rp.parent.mkdir(parents=True, exist_ok=True)
            rp.write_text(lab.risk_analysis_text(KI, st, journal.read(ap.account_dir(KI, fr) / "handel.jsonl")))
    out.update(verarbeitet=res["verarbeitet"], positionen=list(st["positions"]), pausiert=st["paused"], ausgelassen_heute=skipped)
    return out


def submit_orders(live, now=None, root: Path = ROOT, provider=None) -> dict:
    now = now or datetime.now(timezone.utc)
    cfg = load_config(root)
    out = {"eingereicht": [], "abgelehnt": [], "probleme": []}
    if cfg is None:
        return out
    fr = root / "forecast"
    prov = provider or ap.EngineProvider(live, {i["yahoo"]: i for i in cfg["handelsuniversum_instrumente"] + [cfg["benchmark_instrument"]]})
    st = ap.load_state(KI, ap.make_rules(cfg["start"], cfg["ende_exklusiv"], (), version=cfg["experiment"]), root=fr)
    rules, missing, _ = _rules(cfg, prov, st)
    info = str(calendars.last_complete_session("XNYS", now).date())
    if wettbewerb.pd_ge(now, cfg["start"], 0) and now.isoformat() < cfg["ende_exklusiv"]:
        for p in wettbewerb.pending_orders(KI, fr, info, source=SOURCE, offensiv=True):
            try:
                o = p["order"]
                q = live.get(p["instrument"]) if live is not None else prov.qual(p["instrument"]["yahoo"])
                e = ap.submit_order(KI, st, rules, p["prognose_id"], o["limit"], o["stop"], o["ziel"], float(prov.fx().iloc[-1]), q, now=now, root=fr,
                                    allowed=set(rules.UNIVERSE), pj=fr / SOURCE / "prognosen.jsonl")
                out["eingereicht"].append(e["id"])
            except Exception as ex:  # noqa: BLE001
                out["abgelehnt"].append({"prognose_id": p["prognose_id"], "grund": str(ex)})
                journal.append({"typ": "order_abgelehnt", "ki": KI, "prognose_id": p["prognose_id"], "grund": str(ex), "version": rules.VERSION}, path=ap.account_dir(KI, fr) / "handel.jsonl", now=now)
    ap.save_state(KI, st, root=fr)
    return out
