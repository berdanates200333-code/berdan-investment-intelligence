"""Virtuelles Portfolio je KI (10.000 €), eigenes Handelsjournal handel.jsonl (getrennt vom Prognosejournal).

Gleiche Regeln für beide KIs: kein Hebel, keine Leerverkäufe, Gebühr 1 € je Order, Spread+Slippage 0,10 % je Seite,
Währungsumrechnung 0,25 % bei USD, Position <= 25 % des Portfolios, Trade nur mit zuvor journalisierter Prognose
(Prognose-ID, Erstellung VOR dem Trade). Kurse müssen vom Nutzer/Datenroutine verifiziert sein (Quelle im Eintrag).
"""
from __future__ import annotations

from datetime import datetime, timezone

from .. import journal
from . import jr

START_EUR = 10_000.0
FEE, SIDE_COST, FX_FEE, MAX_WEIGHT = 1.0, 0.0010, 0.0025, 0.25


def state(ki: str, hj=None, pj=None) -> dict:
    cash, pos = START_EUR, {}
    for e in journal.read(hj or jr.path(ki, "handel.jsonl")):
        q = pos.setdefault(e["instrument"], {"stueck": 0.0, "kosten_basis_eur": 0.0, "waehrung": e["waehrung"]})
        if e["typ"] == "kauf":
            cash -= e["betrag_eur"]; q["stueck"] += e["stueck"]; q["kosten_basis_eur"] += e["betrag_eur"]
        else:
            cash += e["betrag_eur"]; q["stueck"] -= e["stueck"]
            if q["stueck"] <= 1e-9:
                pos.pop(e["instrument"])
    return {"cash_eur": cash, "positionen": pos}


def trade(ki: str, side: str, prognose_id: str, stueck: float, kurs: float, kurs_quelle: str, fx_usd_per_eur: float | None = None,
          equity_eur: float | None = None, now: datetime | None = None, hj=None, pj=None) -> dict:
    pj = pj or jr.path(ki)
    prog = next((p for p in journal.read(pj) if p["prognose_id"] == prognose_id), None)
    now = now or datetime.now(timezone.utc)
    if prog is None or not prog.get("trade_zulaessig", False):
        raise ValueError("Trade nur mit journalisierter Prognose mit trade_zulaessig=true")
    if prog["erstellt_utc"] >= now.isoformat(timespec="seconds"):
        raise ValueError("Prognose muss vor dem Trade journalisiert sein")
    cur = prog["referenz"]["waehrung"]
    fx = 1.0 if cur == "EUR" else fx_usd_per_eur
    if fx is None:
        raise ValueError("Wechselkurs erforderlich")
    brutto = stueck * kurs / fx
    cost = brutto * SIDE_COST + FEE + (brutto * FX_FEE if cur != "EUR" else 0)
    betrag = brutto + cost if side == "kauf" else brutto - cost
    st = state(ki, hj)
    if side == "kauf":
        eq = equity_eur or st["cash_eur"]
        if betrag > st["cash_eur"] or brutto > MAX_WEIGHT * eq:
            raise ValueError("Barmittel/Positionsgrenze (kein Hebel, max. 25 %)")
    else:
        if st["positionen"].get(prog["instrument"]["id"], {}).get("stueck", 0) < stueck - 1e-9:
            raise ValueError("Leerverkauf nicht erlaubt")
    return journal.append({"typ": side, "prognose_id": prognose_id, "ki": ki, "instrument": prog["instrument"]["id"], "waehrung": cur, "stueck": stueck,
                           "kurs": kurs, "kurs_quelle": kurs_quelle, "fx": fx, "kosten_eur": round(cost, 2), "betrag_eur": round(betrag, 2)},
                          path=hj or jr.path(ki, "handel.jsonl"), now=now)


def valuation(ki: str, last_prices: dict, fx: float, hj=None) -> dict:
    st = state(ki, hj)
    pos_val = {}
    for iid, q in st["positionen"].items():
        px = last_prices.get(iid)
        pos_val[iid] = None if px is None else q["stueck"] * px / (1 if q["waehrung"] == "EUR" else fx)
    missing = [k for k, v in pos_val.items() if v is None]
    total = st["cash_eur"] + sum(v for v in pos_val.values() if v is not None)
    return {"cash_eur": round(st["cash_eur"], 2), "positionen": pos_val, "gesamt_eur": round(total, 2), "kurse_fehlen": missing,
            "rendite": total / START_EUR - 1}
