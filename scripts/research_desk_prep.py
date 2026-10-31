"""Vorbereitung für den täglichen KI-Research-Desk (deterministisch, Python – spart Tokens).

Fasst kompakt zusammen, was die KI-Sitzung braucht, damit sie nicht das ganze Repository lesen muss:
  - Heartbeat (sind Marktcheck und Research-Monitor frisch?)
  - offene Analyseaufträge, bereits analysierte Ereignisse werden ausgefiltert
  - Themengruppen: inhaltlich ähnliche Aufträge desselben Unternehmens -> nur EINE Analyse
  - frühere Analysen je Unternehmen (letzte 30 Tage) -> nur Veränderungen analysieren
  - aktive Investmentideen und Thesenstand

Aufruf: python scripts/research_desk_prep.py  -> JSON auf stdout und in research/desk/prep.json
"""
from __future__ import annotations

import difflib
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bii.research import news  # noqa: E402
from bii.research.events import Store  # noqa: E402
from scripts.heartbeat import check as heartbeat_check  # noqa: E402

STOP = {"the", "and", "for", "with", "its", "as", "to", "of", "in", "on", "a", "an", "is", "are", "stock", "shares",
        "says", "sources", "plans", "expects", "after", "amid", "new"}


def company_words() -> dict[str, set[str]]:
    """Firmennamen/Ticker zählen nicht als gemeinsames Thema (stehen in fast jedem Titel)."""
    import yaml
    cfg = yaml.safe_load((ROOT / "research" / "companies.yaml").read_text())["unternehmen"]
    return {c["ticker"]: set(news.normalize_title(c["name"] + " " + c["ticker"]).split()) for c in cfg}


def keywords(title: str, extra: set[str] = frozenset()) -> set[str]:
    return {w for w in news.normalize_title(title).split() if len(w) > 3 and w not in STOP and w not in extra}


def similar(a: dict, b: dict, names: dict | None = None) -> bool:
    if a["ticker"] != b["ticker"]:
        return False
    extra = (names or {}).get(a["ticker"], set())
    ta, tb = news.normalize_title(a["titel"]), news.normalize_title(b["titel"])
    ka, kb = keywords(a["titel"], extra), keywords(b["titel"], extra)
    inter = ka & kb
    jacc = len(inter) / max(1, len(ka | kb))
    return difflib.SequenceMatcher(None, ta, tb).ratio() >= 0.6 or (len(inter) >= 2 and jacc >= 0.25)


def main(now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    store = Store()
    analysed = {e["bezug"] for e in store.entries if e.get("typ") == "status" and e.get("status") in ("analysiert", "verworfen")}
    queue = []
    for p in sorted((ROOT / "research" / "queue").glob("*.json")):
        q = json.loads(p.read_text())
        ev = q["kontext"]["ereignis"]
        item = {"datei": str(p.relative_to(ROOT)), "ereignis_id": q["ereignis_id"], "ticker": q["ticker"], "titel": q["titel"],
                "art": ev.get("art"), "wichtigkeit": ev.get("wichtigkeit"), "veroeffentlicht": ev.get("veroeffentlicht"),
                "zuverlaessigkeit": ev.get("zuverlaessigkeit"), "quelle": ev.get("quelle", {}).get("url"),
                "quelltext": q["kontext"].get("quelltext"), "grund": q.get("grund"),
                "bereits_analysiert": q["ereignis_id"] in analysed}
        queue.append(item)
    open_items = [q for q in queue if not q["bereits_analysiert"]]
    # Themengruppen bilden (Union-Find über Ähnlichkeit)
    groups: list[list[dict]] = []
    names = company_words()
    for it in sorted(open_items, key=lambda x: x.get("veroeffentlicht") or ""):
        for g in groups:
            if any(similar(it, o, names) for o in g):
                g.append(it)
                break
        else:
            groups.append([it])
    rank = {"hoch": 3, "mittel": 2, "niedrig": 1}
    groups.sort(key=lambda g: (-max(rank.get(x["wichtigkeit"], 0) for x in g), min(x.get("veroeffentlicht") or "" for x in g)))
    # Frühere Analysen je Ticker (30 Tage)
    cutoff = (now - timedelta(days=30)).date().isoformat()
    prior: dict[str, list[dict]] = {}
    for f in sorted((ROOT / "research" / "analyses").glob("*.md")):
        m = re.match(r"(\d{4}-\d{2}-\d{2})_([A-Z]+)_(.+)\.md", f.name)
        if not m or m.group(1) < cutoff:
            continue
        text = f.read_text()
        head = re.search(r"^# (.+)$", text, re.M)
        verdict = re.search(r"## 6\..*?\n\*\*(.+?)\*\*", text, re.S)
        prior.setdefault(m.group(2), []).append({"datei": str(f.relative_to(ROOT)), "datum": m.group(1),
                                                 "titel": head.group(1) if head else f.name,
                                                 "thesenwirkung": verdict.group(1)[:160] if verdict else None})
    ideas = []
    idx = ROOT / "research" / "ideas" / "index.jsonl"
    if idx.exists():
        latest: dict[str, dict] = {}
        for line in idx.read_text().splitlines():
            if line.strip():
                d = json.loads(line)
                latest[d["id"]] = d
        ideas = [d for d in latest.values() if d.get("status") in ("beobachten", "aktiv")]
    theses = {}
    for f in (ROOT / "research" / "theses").glob("*.json"):
        t = json.loads(f.read_text())
        theses[t["ticker"]] = {"version": t["version"], "stand": t["stand"], "letzte_aenderung": t["historie"][-1]}
    hb = heartbeat_check(now)
    out = {"erstellt_utc": now.isoformat(timespec="seconds"),
           "heartbeat": {"ok": not hb, "probleme": hb},
           "offene_auftraege": len(open_items), "bereits_analysiert_uebersprungen": len(queue) - len(open_items),
           "themengruppen": [{"ticker": g[0]["ticker"], "anzahl": len(g), "wichtigkeit_max": max((x["wichtigkeit"] for x in g), key=lambda w: rank.get(w, 0)),
                              "auftraege": g, "fruehere_analysen": prior.get(g[0]["ticker"], [])} for g in groups],
           "aktive_ideen": ideas, "thesen": theses,
           "budget": {"max_tiefenanalysen": 3, "hinweis": "Gruppen ab Platz 4 nur als Kurznotiz; bereits analysierte Themen nur bei neuen Fakten"}}
    d = ROOT / "research" / "desk"
    d.mkdir(parents=True, exist_ok=True)
    (d / "prep.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return out


if __name__ == "__main__":
    main()
