"""Append-only Handelsjournal mit Hash-Kette.

Jeder Eintrag enthält den SHA-256-Hash des vorherigen Eintrags. Eine nachträgliche
Änderung eines alten Signals bricht die Kette und wird von verify() erkannt.
Zusätzlich liegt das Journal in Git: jeder Commit ist ein zeitgestempelter Nachweis.
Korrekturen erfolgen ausschließlich durch NEUE Einträge (typ 'korrektur'), nie durch Überschreiben.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JOURNAL = ROOT / "journal" / "journal.jsonl"
GENESIS = "0" * 64


def _hash(entry: dict) -> str:
    body = {k: v for k, v in entry.items() if k != "hash"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def read(path: Path = JOURNAL) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def append(entry: dict, path: Path = JOURNAL) -> dict:
    entries = read(path)
    prev = entries[-1]["hash"] if entries else GENESIS
    e = {"seq": len(entries) + 1,
         "erstellt_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
         **entry, "prev_hash": prev}
    e["hash"] = _hash(e)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(e, ensure_ascii=False, sort_keys=True) + "\n")
    return e


def verify(path: Path = JOURNAL) -> tuple[bool, str]:
    prev = GENESIS
    for i, e in enumerate(read(path), 1):
        if e.get("seq") != i:
            return False, f"Sequenzfehler bei Eintrag {i}"
        if e.get("prev_hash") != prev:
            return False, f"Kette gebrochen bei Eintrag {i}"
        if _hash(e) != e.get("hash"):
            return False, f"Eintrag {i} wurde verändert"
        prev = e["hash"]
    return True, "Journal intakt"
