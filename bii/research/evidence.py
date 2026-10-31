"""Belegprüfung kuratierter Angaben im Text der jüngsten Pflichtveröffentlichung (10-K).

Eine kuratierte Beziehung oder Managementangabe gilt nur als "im 10-K belegt", wenn ihr
Prüfwort im Text vorkommt. Gespeichert wird ein kurzer Textausschnitt als Nachweis.
Das ist eine Textsuche, kein Verständnis des Zusammenhangs: der Ausschnitt muss gelesen werden.
"""
from __future__ import annotations

import re


def snippet(text: str, word: str, width: int = 160) -> str | None:
    m = re.search(re.escape(word), text, flags=re.IGNORECASE if word.islower() else 0)
    if not m:
        return None
    a, b = max(0, m.start() - width), min(len(text), m.end() + width)
    return re.sub(r"\s+", " ", text[a:b]).strip()


def check(text: str, items: list[dict]) -> list[dict]:
    out = []
    for it in items:
        w = it.get("pruefwort")
        s = snippet(text, w) if w else None
        n = len(re.findall(re.escape(w), text)) if w else 0
        out.append({**it, "beleg": "im 10-K gefunden" if s else "im 10-K nicht gefunden – unbestätigt",
                    "treffer": n, "ausschnitt": s})
    return out


def item1_excerpt(text: str, length: int = 1500) -> str | None:
    """Beginn von 'Item 1. Business' (nach dem Inhaltsverzeichnis)."""
    hits = [m.start() for m in re.finditer(r"(?i)item\s*1\.?\s*business", text)]
    for h in hits[1:] + hits[:1]:
        seg = text[h:h + length + 200]
        if len(re.sub(r"\s+", " ", seg)) > 600 and not re.search(r"(?i)item\s*1a", seg[:300]):
            return re.sub(r"\s+", " ", seg[:length]).strip()
    return None
