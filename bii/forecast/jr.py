"""Prognosejournal (append-only, Hash-Kette) je KI. Reine Prognosen, getrennt von Handelsjournalen.

Pflichtfelder werden geprüft; Zielkurse werden aus Referenzkurs und Prozentprognose berechnet (keine Handeingabe).
Korrekturen = NEUE Prognose mit eigener ID (Feld 'ersetzt'), alte bleibt auswertbar.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .. import journal
from . import calendars

ROOT = Path(__file__).resolve().parents[2]
REGELVERSION = "FC1-1.0"
KIS = ("claude", "chatgpt")
HORIZONTE = (1, 5, 20)
ENTSCHEIDUNGEN = ("KAUFEN", "HALTEN", "VERKAUFEN", "NICHT KAUFEN")
PFLICHT = ("prognose_id", "ki", "instrument", "referenz", "horizonte", "entscheidung", "gruende", "gegenargumente",
           "falsifikation", "quellen", "belastbarkeit")


def phase() -> str:
    """'pilot' bis der Wettbewerb gemäß Startnachweis (forecast/wettbewerb.json) offiziell gestartet ist."""
    f = ROOT / "forecast" / "wettbewerb.json"
    try:
        return "wettbewerb" if json.loads(f.read_text()).get("status") == "gestartet" else "pilot"
    except (OSError, ValueError):
        return "pilot"


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
    if p.get("trade_zulaessig"):
        o = p.get("order") or {}
        if not all(isinstance(o.get(k), (int, float)) and o[k] > 0 for k in ("limit", "stop", "ziel")):
            raise ValueError("trade_zulaessig verlangt order {limit, stop, ziel}")
    if p["belastbarkeit"] not in ("belastbar", "eingeschraenkt", "nicht_belastbar"):
        raise ValueError("belastbarkeit ungültig")


def add(p: dict, now: datetime | None = None, ki_path: Path | None = None) -> dict:
    validate(p)
    jp = ki_path or path(p["ki"])
    if any(e["prognose_id"] == p["prognose_id"] for e in journal.read(jp)):
        raise ValueError("Prognose-ID existiert bereits (kein Überschreiben)")
    now = now or datetime.now(timezone.utc)
    if phase() == "wettbewerb":
        from . import universe
        if p["instrument"]["yahoo"] not in universe.admitted():
            raise ValueError("Instrument nicht im zugelassenen Universum (Datenstufe A + Liquidität)")
        ref = next((i for i in universe.load()["stufe1_handelbar"] if i["yahoo"] == p["instrument"]["yahoo"]), None)
        if ref is None:
            raise ValueError("Instrument ist nicht handelbar (nur Stufe-1-Universum)")
        p = {**p, "instrument": {**ref, "name": p["instrument"].get("name", ref["id"])}}      # Identität (ISIN/Börse/Währung/Klasse) kommt aus dem Universum, nicht von der KI
    venue = calendars.venue_of(p["instrument"])
    expected = calendars.horizon_dates(venue, p["referenz"]["datum"])
    for h in HORIZONTE:
        if p["horizonte"][str(h)]["zieltermin"] != expected[str(h)]:
            raise ValueError(f"Zieltermin {h} Handelstage passt nicht zum Börsenkalender {venue}: erwartet {expected[str(h)]}")
    if not calendars.forecast_deadline_ok(venue, expected["1"], now):
        raise ValueError("Bewertungszeitraum hat bereits begonnen (Eröffnung des 1-Tages-Zieltags laut Börsenkalender) – nachträgliche Prognose unzulässig")
    info = calendars.last_complete_session(venue, now)
    if str(info.date()) != p["referenz"]["datum"]:
        raise ValueError(f"Informationsstichtag: Referenzdatum muss der letzte abgeschlossene Handelstag sein ({info.date()}), nicht {p['referenz']['datum']}")
    p = {**p, "phase": phase()}
    p = {**p, "regelversion": REGELVERSION, "typ": "prognose"}
    for h in HORIZONTE:
        x = p["horizonte"][str(h)]
        x["zielkurs"] = round(p["referenz"]["kurs"] * (1 + x["erwartung_pct"] / 100), 4)
    return journal.append(p, path=jp, now=now)
