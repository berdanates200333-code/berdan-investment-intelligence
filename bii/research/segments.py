"""Umsatzsegmente aus der XBRL-Instanz einer Einreichung (dimensionale Fakten).

companyfacts enthält keine Segmentdaten. Deshalb wird die von EDGAR bereitgestellte
Instanzdatei (*_htm.xml) gelesen. Ausgewertet werden Umsatzfakten, deren Kontext genau
ein Dimensionsmitglied auf einer der Achsen unten hat.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import date

AXES = {
    "StatementBusinessSegmentsAxis": "Geschäftssegmente",
    "ProductOrServiceAxis": "Produkte/Dienstleistungen",
    "StatementGeographicalAxis": "Regionen",
}
REVENUE = ("RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet")
OPINC = ("OperatingIncomeLoss",)
XBRLI = "{http://www.xbrl.org/2003/instance}"
XBRLDI = "{http://xbrl.org/2006/xbrldi}"


def humanize(member: str) -> str:
    name = member.split(":")[-1]
    name = re.sub(r"(SegmentMember|Member)$", "", name)
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", name).strip()


def parse(xml_bytes: bytes) -> dict:
    root = ET.fromstring(xml_bytes)
    ctx = {}
    for c in root.iter(f"{XBRLI}context"):
        cid = c.get("id")
        per = c.find(f"{XBRLI}period")
        start, end = per.find(f"{XBRLI}startDate"), per.find(f"{XBRLI}endDate")
        if start is None or end is None:
            continue
        mems = [(m.get("dimension"), (m.text or "").strip()) for m in c.iter(f"{XBRLDI}explicitMember")]
        typed = list(c.iter(f"{XBRLDI}typedMember"))
        ctx[cid] = {"start": start.text.strip(), "end": end.text.strip(), "members": mems, "typed": bool(typed)}
    facts = []
    for el in root:
        tag = el.tag.split("}")[-1]
        if tag not in REVENUE + OPINC or el.get("contextRef") not in ctx or not (el.text or "").strip():
            continue
        c = ctx[el.get("contextRef")]
        try:
            val = float(el.text)
        except ValueError:
            continue
        facts.append({"konzept": tag, "wert": val, **c})
    return _summarize(facts)


def _days(f):
    return (date.fromisoformat(f["end"]) - date.fromisoformat(f["start"])).days


def _summarize(facts: list[dict]) -> dict:
    if not facts:
        return {}
    # Berichtszeitraum = jüngstes Periodenende; Dauer: Jahr bevorzugt, sonst Quartal
    totals = [f for f in facts if not f["members"] and not f["typed"] and f["konzept"] in REVENUE]
    if not totals:
        return {}
    end = max(f["end"] for f in totals)
    cand = [f for f in totals if f["end"] == end]
    period = max(cand, key=_days)
    start = period["start"]
    rev_concept = period["konzept"]
    out = {"periode": {"von": start, "bis": end, "tage": _days(period)}, "gesamtumsatz": period["wert"],
           "umsatzkonzept": rev_concept, "achsen": {}}
    for f in facts:
        if f["start"] != start or f["end"] != end or len(f["members"]) != 1 or f["typed"]:
            continue
        dim, mem = f["members"][0]
        axis = dim.split(":")[-1]
        if axis not in AXES:
            continue
        kind = "umsatz" if f["konzept"] == rev_concept else ("operatives_ergebnis" if f["konzept"] in OPINC else None)
        if kind is None:
            continue
        a = out["achsen"].setdefault(AXES[axis], {})
        a.setdefault(humanize(mem), {})[kind] = f["wert"]
    for name, segs in out["achsen"].items():
        tot = sum(v.get("umsatz", 0) for v in segs.values())
        for v in segs.values():
            if "umsatz" in v and out["gesamtumsatz"]:
                v["anteil"] = v["umsatz"] / out["gesamtumsatz"]
        out.setdefault("abdeckung", {})[name] = tot / out["gesamtumsatz"] if out["gesamtumsatz"] else None
    return out
