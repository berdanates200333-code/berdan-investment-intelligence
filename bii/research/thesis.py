"""Investmentthesen mit maschinenprüfbaren Bedingungen.

research/desk/theses/<TICKER>.json enthält:
- Text (Kernthese, Kurstreiber, Risiken, Gegenargumente) – von Claude oder dir verfasst, gekennzeichnet
- Szenarien (negativ/neutral/positiv) mit numerischen Annahmen → Wert je Aktie (valuation.scenario_value)
- einstiegskriterien / widerlegung: Liste von {id, text, pruefung: {metrik, op, wert, n?}}
  Prüfung ist eine REGEL in Python. Bedingungen ohne 'pruefung' gelten als „manuell zu prüfen“.

Metriken (aus financials.kennzahlen, valuation und Kurs):
  umsatzwachstum_yoy_q, bruttomarge_q, operative_marge_q, fcf_marge_ttm, nettoliquiditaet,
  kgv_ttm, ev_umsatz_ttm, fcf_rendite_ttm, kurs_zu_basiswert (Kurs / Basisszenario-Wert heute),
  umsatzwachstum_yoy_letzte_n (alle der letzten n Quartale), bruttomarge_letzte_n
"""
from __future__ import annotations

import json
import operator
from pathlib import Path

from . import valuation
from .store import R

OPS = {"<": operator.lt, "<=": operator.le, ">": operator.gt, ">=": operator.ge}


def load(ticker: str) -> dict | None:
    p = R / "theses" / f"{ticker}.json"
    return json.loads(p.read_text()) if p.exists() else None


def metric_values(name: str, k: dict, mult: dict, ratio_to_base: float | None, n: int | None) -> list[float] | None:
    if name == "kurs_zu_basiswert":
        return None if ratio_to_base is None else [ratio_to_base]
    if name == "umsatzwachstum_yoy_letzte_n":
        vals = [x["wachstum"] for x in k.get("umsatzwachstum_yoy_hist", []) if x["wachstum"] is not None][-(n or 2):]
        return vals if len(vals) == (n or 2) else None
    if name == "bruttomarge_letzte_n":
        vals = [x["marge"] for x in k.get("bruttomarge_hist", []) if x["marge"] is not None][-(n or 2):]
        return vals if len(vals) == (n or 2) else None
    v = k.get(name, mult.get(name))
    return None if v is None else [v]


def evaluate(th: dict, fin: dict, px: dict, mult: dict) -> dict:
    k = fin.get("kennzahlen", {})
    shares = (fin.get("aktien_ausstehend") or {}).get("wert")
    scen = []
    base_today = None
    for sc in th.get("szenarien", []):
        if k.get("umsatz_ttm") and shares:
            v = valuation.scenario_value(sc, k, shares, k.get("nettoliquiditaet", 0.0))
            v["rendite_pa_ab_kurs"] = ((v["wert_je_aktie_zieljahr"] / px["kurs"]) ** (1 / sc.get("jahre", 5)) - 1
                                       if px.get("kurs") else None)
            scen.append({**sc, "ergebnis": v})
            if sc.get("name") == "neutral":
                base_today = v["wert_je_aktie_heute"]
    ratio = px["kurs"] / base_today if base_today and px.get("kurs") else None

    def check(items):
        out = []
        for c in items:
            p = c.get("pruefung")
            if not p:
                out.append({**c, "status": "manuell", "erfuellt": None})
                continue
            vals = metric_values(p["metrik"], k, mult, ratio, p.get("n"))
            if vals is None:
                out.append({**c, "status": "keine_daten", "erfuellt": None})
                continue
            ok = all(OPS[p["op"]](v, p["wert"]) for v in vals)
            out.append({**c, "status": "geprueft", "erfuellt": ok, "istwerte": [round(v, 4) for v in vals]})
        return out

    return {"szenarien": scen, "kurs_zu_basiswert": ratio,
            "einstieg": check(th.get("einstiegskriterien", [])),
            "widerlegung": check(th.get("widerlegung", []))}
