"""Anlageuniversum (gemeinsam für beide KIs). Zulassung nur mit Datenstufe A und ausreichender Liquidität."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from . import quality

ROOT = Path(__file__).resolve().parents[2]
U = ROOT / "forecast" / "universum.json"
STATUS = ROOT / "forecast" / "universum_status.json"


def load() -> dict:
    return json.loads(U.read_text())


def check_universe(live, now) -> dict:
    """Prüft alle Stufe-1-Instrumente und Benchmarks live; schreibt den Status (Zulassung = Stufe A + Liquidität)."""
    u = load()
    out = {"geprueft_utc": pd.Timestamp(now).isoformat(), "universum_version": u["version"], "instrumente": {}}
    for inst in u["stufe1_handelbar"] + u["benchmarks"]:
        q = live.get(inst)
        if q is None:
            out["instrumente"][inst["id"]] = {"zugelassen": False, "stufe": quality.C, "grund": ["keine Daten"]}
            continue
        d = q.df.index[-1]
        adv = float((q.df.close * q.df.volume).tail(20).mean())
        tier, ok_t = q.tier_at(d), None
        ok_t = quality.RANK[tier] >= quality.RANK[quality.A]
        liquid = inst in u["benchmarks"] or adv >= u["mindest_dollarvolumen_20t"]
        out["instrumente"][inst["id"]] = {"zugelassen": bool(ok_t and liquid), "stufe": tier, "letzter_balken": str(d.date()), "dollarvolumen_20t_mio": round(adv / 1e6, 1),
                                          "zweitquelle": q.secondary_name, "gruende": q.reasons + ([] if liquid else ["Liquidität unter Schwelle"])}
    return out


def admitted() -> set:
    try:
        st = json.loads(STATUS.read_text())["instrumente"]
    except (OSError, ValueError, KeyError):
        return set()
    return {k for k, v in st.items() if v.get("zugelassen")}
