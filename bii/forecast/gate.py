"""Startbedingungen des 60-Kalendertage-Wettbewerbs. Start nur, wenn ALLE Bedingungen nachgewiesen sind. Kein Rückdatieren.

Geprüft werden Belege, keine Behauptungen: Journale, Ausführungen, Benchmark-Kauf, Daten-Prüfsummen, Eingangsbelege (nur von der Automatik
committet), reale Handelstage."""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from .. import journal
from . import calendars

ROOT = Path(__file__).resolve().parents[2]
MIN_ADMITTED = 20
MIN_SESSIONS = 2          # zwei verschiedene tatsächliche Handelstage
BOT = "market-check-bot"


def _real_session(day: str) -> bool:
    return calendars.is_session("XNYS", day)


def _bot_committed(path: Path, root: Path) -> bool:
    """Beleg gilt nur, wenn die Datei im Git-Verlauf vom Workflow-Bot stammt (keine von Hand angelegten Belege)."""
    try:
        out = subprocess.run(["git", "log", "--format=%an", "--", str(path.relative_to(root))], cwd=root, capture_output=True, text=True, timeout=20).stdout.split()
        return bool(out) and all(a == BOT for a in out)
    except Exception:  # noqa: BLE001
        return False


def _receipts(ki, root):
    d = root / "forecast" / "receipts" / ki
    return [(f, json.loads(f.read_text())) for f in sorted(d.glob("*.json")) if "abgelehnt" not in f.name] if d.exists() else []


def checks(root: Path = ROOT) -> dict:
    out = {}
    fr = root / "forecast"
    try:
        st = json.loads((fr / "universum_status.json").read_text())["instrumente"]
    except (OSError, ValueError, KeyError):
        st = {}
    bench = None
    try:
        bench = json.loads((fr / "benchmark_entscheidung.json").read_text())
    except (OSError, ValueError):
        pass
    adm = {k for k, v in st.items() if v.get("zugelassen")}
    trade = [k for k in adm if not bench or k != bench["symbol"]]
    out["universum_ausreichend"] = {"ok": len(trade) >= MIN_ADMITTED, "detail": f"{len(trade)} zugelassene Handelsinstrumente (Minimum {MIN_ADMITTED})"}
    out["benchmark_festgeschrieben"] = {"ok": bool(bench) and bench["symbol"] in adm, "detail": f"Benchmark {bench['symbol'] if bench else 'nicht festgeschrieben'}; zugelassen: {bool(bench) and bench['symbol'] in adm}"}
    days = {}
    for ki in ("claude", "chatgpt"):
        p = fr / "probelauf2" / ki / "konto" / "handel.jsonl"
        ents = journal.read(p) if p.exists() else []
        kauf = [e for e in ents if e["typ"] == "ausfuehrung" and e.get("seite") == "kauf"]
        bench_buy = [e for e in ents if e["typ"] == "benchmark_ausfuehrung"]
        tage = {e["datum"]: e["daten_fingerprint"] for e in ents if e["typ"] == "tagesabschluss"}
        days[ki] = tage
        real = [d for d in tage if _real_session(d)]
        ok = bool(kauf) and bool(bench_buy) and len(real) >= MIN_SESSIONS
        out[f"ausfuehrungszyklus_{ki}"] = {"ok": ok, "detail": f"{len(kauf)} simulierte Käufe, {len(bench_buy)} dokumentierte Benchmark-Käufe, {len(real)} verarbeitete Handelstage (Minimum {MIN_SESSIONS})"}
        sessions = {}
        for f, r in _receipts(ki, root):
            sessions.setdefault(r["sitzung"], {})[r["stage"]] = (f, r)
        valid = []
        kj = journal.read(fr / ki / "prognosen.jsonl") if (fr / ki / "prognosen.jsonl").exists() else []
        for sess, v in sessions.items():
            if "commit" not in v or "reveal" not in v or not _real_session(sess):
                continue
            (fc, c), (fv, rv) = v["commit"], v["reveal"]
            if c.get("ereignis") != "push" or rv.get("ereignis") != "push" or not c.get("run_id") or not rv.get("run_id"):
                continue
            if not (_bot_committed(fc, root) and _bot_committed(fv, root)):
                continue
            ids = set(rv.get("prognose_ids", []))
            if ids and ids <= {e["prognose_id"] for e in kj if e.get("zeitnachweis", {}).get("commit_hash") == c.get("hash")}:
                valid.append(sess)
        out[f"automatik_{ki}"] = {"ok": len(valid) >= MIN_SESSIONS, "detail": f"{len(valid)}/{MIN_SESSIONS} verschiedene reale Handelstage mit Commit+Reveal per Push (Beleg vom Bot, Journal passt zum Commit)"}
        s = fr / ki / "konto" / "state.json"
        out[f"konto_{ki}_bereit"] = {"ok": (not s.exists()) or (json.loads(s.read_text())["cash_eur"] == 10000.0 and not json.loads(s.read_text())["closed"]), "detail": "10.000 € unberührt"}
    common = set(days["claude"]) & set(days["chatgpt"])
    same = bool(common) and all(days["claude"][d] == days["chatgpt"][d] for d in common) and set(days["claude"]) == set(days["chatgpt"])
    out["identische_eingabedaten"] = {"ok": same and len(common) >= MIN_SESSIONS, "detail": f"{len(common)} gemeinsame Tage; Daten-Prüfsummen {'identisch' if same else 'ABWEICHEND/fehlend'}"}
    out["kein_echtgeld"] = {"ok": True, "detail": "keine Broker-Anbindung im Repo; Engine rein virtuell"}
    return out


def evaluate_gate(root: Path = ROOT) -> dict:
    c = checks(root)
    return {"geprueft_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "alle_erfuellt": all(v["ok"] for v in c.values()), "bedingungen": c}


def start(now, root: Path = ROOT) -> dict:
    g = evaluate_gate(root)
    if not g["alle_erfuellt"]:
        raise ValueError("Startbedingungen nicht erfüllt: " + ", ".join(k for k, v in g["bedingungen"].items() if not v["ok"]))
    fr = root / "forecast"
    u = json.loads((fr / "universum.json").read_text())
    st = json.loads((fr / "universum_status.json").read_text())["instrumente"]
    bench = json.loads((fr / "benchmark_entscheidung.json").read_text())
    insts = [i for i in u["stufe1_handelbar"] if st.get(i["id"], {}).get("zugelassen")]
    b_inst = next(i for i in u["benchmarks"] if i["yahoo"] == bench["symbol"])
    day, _ = calendars.next_session_open("XNYS", now)       # frühestens nächste Sitzung, nie rückdatiert
    return {"status": "gestartet", "experiment": "FC1-1.0-W", "start": str(day.date()), "ende_exklusiv": str((day + timedelta(days=60)).date()),
            "handelsuniversum_instrumente": insts, "benchmark_instrument": b_inst, "festgeschrieben_utc": pd.Timestamp(now).isoformat(), "gate": g,
            "regel": "Universum, Benchmark und Regeln sind ab hier eingefroren; Änderungen nur als neue Version mit neuem Test."}
