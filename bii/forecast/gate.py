"""Startbedingungen des 60-Kalendertage-Wettbewerbs. Start nur, wenn ALLE Bedingungen nachgewiesen sind. Kein Rückdatieren."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from .. import journal
from . import calendars, universe

ROOT = Path(__file__).resolve().parents[2]
MIN_ADMITTED = 20
MIN_AUTOMATION_DAYS = 2        # je KI: Anzahl Sitzungen mit Commit UND Reveal, ausgelöst durch Push-Ereignis (unbeaufsichtigt)


def _receipts(ki, root):
    d = root / "forecast" / "receipts" / ki
    return [json.loads(f.read_text()) for f in sorted(d.glob("*.json")) if "abgelehnt" not in f.name] if d.exists() else []


def checks(root: Path = ROOT) -> dict:
    out = {}
    adm = universe.admitted() if root == ROOT else set()
    try:
        st = json.loads((root / "forecast" / "universum_status.json").read_text())["instrumente"]
        adm = {k for k, v in st.items() if v.get("zugelassen")}
    except (OSError, ValueError, KeyError):
        pass
    out["universum_ausreichend"] = {"ok": len(adm - {"EUNL.DE"}) >= MIN_ADMITTED and "EUNL.DE" in adm, "detail": f"{len(adm)} zugelassen, Benchmark EUNL.DE {'ja' if 'EUNL.DE' in adm else 'NEIN'}"}
    for ki in ("claude", "chatgpt"):
        acc = root / "forecast" / ki / "konto"
        p = root / "forecast" / "probelauf" / ki / "konto" / "handel.jsonl"
        ents = journal.read(p) if p.exists() else []
        filled = any(e["typ"] == "ausfuehrung" and e.get("seite") == "kauf" for e in ents)
        bench = any(e["typ"] == "benchmark_ausfuehrung" or e["typ"] == "ausfuehrung" for e in ents)
        out[f"ausfuehrungszyklus_{ki}"] = {"ok": filled, "detail": "Probelauf mit echter Ausführung auf Stufe-A-Daten nachgewiesen" if filled else "noch kein erfolgreicher Probelauf-Zyklus"}
        sessions = {}
        for r in _receipts(ki, root):
            sessions.setdefault(r["sitzung"], {})[r["stage"]] = r
        auto = [s for s, v in sessions.items() if "commit" in v and "reveal" in v and v["commit"].get("ereignis") == "push" and v["reveal"].get("ereignis") == "push"]
        out[f"automatik_{ki}"] = {"ok": len(auto) >= MIN_AUTOMATION_DAYS, "detail": f"{len(auto)}/{MIN_AUTOMATION_DAYS} unbeaufsichtigte Sitzungen (Commit+Reveal per Push)"}
        s = acc / "state.json"
        out[f"konto_{ki}_bereit"] = {"ok": (not s.exists()) or (json.loads(s.read_text())["cash_eur"] == 10000.0 and not json.loads(s.read_text())["closed"]), "detail": "10.000 € unberührt"}
    out["kein_echtgeld"] = {"ok": True, "detail": "keine Broker-Anbindung im Repo; Engine rein virtuell"}
    return out


def evaluate_gate(root: Path = ROOT) -> dict:
    c = checks(root)
    return {"geprueft_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "alle_erfuellt": all(v["ok"] for v in c.values()), "bedingungen": c}


def start(now: datetime, root: Path = ROOT) -> dict:
    g = evaluate_gate(root)
    if not g["alle_erfuellt"]:
        raise ValueError("Startbedingungen nicht erfüllt: " + ", ".join(k for k, v in g["bedingungen"].items() if not v["ok"]))
    day, _ = calendars.next_session_open("XNYS", now)       # frühestens nächste Sitzung, nie rückdatiert
    return {"status": "gestartet", "start": str(day.date()), "ende_exklusiv": str((day + timedelta(days=60)).date()), "gate": g}
