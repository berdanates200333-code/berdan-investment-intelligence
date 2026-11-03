"""Prognosejournal (append-only, Hash-Kette) je KI. Reine Prognosen, getrennt von Handelsjournalen.

Pflichtfelder werden geprüft; Zielkurse werden aus Referenzkurs und Prozentprognose berechnet (keine Handeingabe).
Korrekturen = NEUE Prognose mit eigener ID (Feld 'ersetzt'), alte bleibt auswertbar.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .. import journal

ROOT = Path(__file__).resolve().parents[2]
REGELVERSION = "FC1-1.0"
KIS = ("claude", "chatgpt")
HORIZONTE = (1, 5, 20)
ENTSCHEIDUNGEN = ("KAUFEN", "HALTEN", "VERKAUFEN", "NICHT KAUFEN")
PFLICHT = ("prognose_id", "ki", "instrument", "referenz", "horizonte", "entscheidung", "gruende", "gegenargumente",
           "falsifikation", "quellen", "belastbarkeit")


def path(ki: str, name: str = "prognosen.jsonl") -> Path:
    assert ki in KIS
    return ROOT / "forecast" / ki / name


def validate(p: dict) -> None:
    for k in PFLICHT:
        if p.get(k) in (None, "", [], {}):
            raise ValueError(f"Pflichtfeld fehlt: {k}")
    if p["ki"] not in KIS or p["entscheidung"] not in ENTSCHEIDUNGEN:
        raise ValueError("ki/entscheidung ungültig")
    r = p["referenz"]
    for k in ("kurs", "waehrung", "datum", "quelle"):
        if not r.get(k):
            raise ValueError(f"Referenz unvollständig: {k}")
    for h in HORIZONTE:
        x = p["horizonte"].get(str(h))
        if not x or not (0 < x["p_positiv"] < 1) or "erwartung_pct" not in x or not x.get("zieltermin"):
            raise ValueError(f"Horizont {h} unvollständig")
    if p["belastbarkeit"] not in ("belastbar", "eingeschraenkt", "nicht_belastbar"):
        raise ValueError("belastbarkeit ungültig")


def add(p: dict, now: datetime | None = None, ki_path: Path | None = None) -> dict:
    validate(p)
    jp = ki_path or path(p["ki"])
    if any(e["prognose_id"] == p["prognose_id"] for e in journal.read(jp)):
        raise ValueError("Prognose-ID existiert bereits (kein Überschreiben)")
    p = {**p, "regelversion": REGELVERSION, "typ": "prognose"}
    for h in HORIZONTE:
        x = p["horizonte"][str(h)]
        x["zielkurs"] = round(p["referenz"]["kurs"] * (1 + x["erwartung_pct"] / 100), 4)
    return journal.append(p, path=jp, now=now)
