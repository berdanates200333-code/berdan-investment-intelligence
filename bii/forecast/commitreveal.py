"""Commit-Reveal für faire, blinde Tagesprognosen (technisch erzwungen, serverseitige Zeitstempel).

Ablauf je Sitzung S (erste bewertete Sitzung, Eröffnung laut Börsenkalender):
  1. COMMIT (bis S_open - COMMIT_LEAD): jede KI legt nur sha256(nonce + kanonisches JSON der Prognosen) ab. Inhalt bleibt unsichtbar.
  2. REVEAL (ab Cutoff bis S_open): Klartext + nonce. Der Eingangsdienst (GitHub Actions) prüft Hash, Fristen und Informationsstichtag und
     übernimmt erst dann in das Prognosejournal. Zeitstempel = Laufzeit des Eingangsdienstes (Server), nie der Inhalt.
  Eine KI kann ihre Prognose nach Kenntnis der anderen weder ändern (Hash) noch rechtzeitig ersetzen; verfrühter Reveal wird abgelehnt
  und für diese Sitzung disqualifiziert. Grenze: Zwischen Sitzungen sind veröffentlichte Klartexte im gemeinsamen Repo lesbar
  (Härtung: getrenntes, privates Eingangs-Repo mit schreibenden Deploy-Keys je KI).
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from .. import journal
from . import calendars, jr

ROOT = Path(__file__).resolve().parents[2]
COMMIT_LEAD = timedelta(minutes=60)


def canonical(prognosen: list) -> bytes:
    return json.dumps(prognosen, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()


def commitment(prognosen: list, nonce: str) -> str:
    return hashlib.sha256(nonce.encode() + b"|" + canonical(prognosen)).hexdigest()


def windows(venue: str, now) -> dict:
    day, opening = calendars.next_session_open(venue, now)
    return {"sitzung": str(day.date()), "oeffnung_utc": opening.isoformat(), "cutoff_utc": (opening - COMMIT_LEAD).isoformat()}


def receipt_path(ki: str, sitzung: str, stage: str, root: Path = ROOT) -> Path:
    return root / "forecast" / "receipts" / ki / f"{sitzung}.{stage}.json"


def _write_receipt(path: Path, doc: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as f:           # 'x': nie überschreiben
        f.write(json.dumps(doc, indent=1, ensure_ascii=False))


def ingest(ki: str, sitzung: str, stage: str, payload: dict, now: datetime, event: str, venue: str = "XNYS", root: Path = ROOT, jpath: Path | None = None) -> dict:
    """Verarbeitet eine Commit- oder Reveal-Datei. 'now' = Serverzeit des Eingangsdienstes. Rückgabe: Beleg."""
    day, opening = calendars.next_session_open(venue, now)
    cutoff = opening - COMMIT_LEAD
    if str(day.date()) != sitzung:
        raise ValueError(f"Datei gehört zu Sitzung {sitzung}, aktuell offen ist {day.date()}")
    now_ts = pd.Timestamp(now)
    if stage == "commit":
        if now_ts >= cutoff:
            raise ValueError("Commit nach Cutoff – abgelehnt")
        doc = {"ki": ki, "sitzung": sitzung, "stage": "commit", "hash": payload["hash"], "server_utc": now.isoformat(timespec="seconds"), "ereignis": event}
        _write_receipt(receipt_path(ki, sitzung, "commit", root), doc)
        return doc
    if stage != "reveal":
        raise ValueError("stage ungültig")
    cp = receipt_path(ki, sitzung, "commit", root)
    if not cp.exists():
        raise ValueError("Kein Commit vorhanden – Reveal abgelehnt")
    if now_ts < cutoff:
        raise ValueError("Reveal vor Cutoff – abgelehnt (Sitzung für diese KI disqualifiziert)")
    if now_ts >= opening:
        raise ValueError("Reveal nach Eröffnung – abgelehnt")
    commit = json.loads(cp.read_text())
    if commitment(payload["prognosen"], payload["nonce"]) != commit["hash"]:
        raise ValueError("Hash stimmt nicht mit dem Commit überein – abgelehnt")
    ids = []
    for p in payload["prognosen"]:
        p = {**p, "ki": ki, "zeitnachweis": {"commit_utc": commit["server_utc"], "reveal_utc": now.isoformat(timespec="seconds"), "commit_hash": commit["hash"]}}
        ids.append(jr.add(p, now=now, ki_path=jpath)["prognose_id"])
    doc = {"ki": ki, "sitzung": sitzung, "stage": "reveal", "prognose_ids": ids, "server_utc": now.isoformat(timespec="seconds"), "ereignis": event}
    _write_receipt(receipt_path(ki, sitzung, "reveal", root), doc)
    return doc
