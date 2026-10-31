"""RSS/Atom-Quellen: offizielle Unternehmens-Newsrooms und Nachrichten-Aggregatoren (kostenlos, ohne Schlüssel).

- Offizielle Newsroom-/IR-Feeds: Primärquelle für Unternehmensmitteilungen.
- Google News RSS / Yahoo Finance RSS: Aggregatoren (Sekundärquellen). Nur Metadaten werden gespeichert.
Nutzungshinweis: Die Feeds sind für den persönlichen Abruf gedacht; Abfragen sparsam (≤ 3×/Tag).
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from datetime import timezone
from urllib.parse import quote_plus, urlsplit

import requests

UA = {"User-Agent": "Mozilla/5.0 (personal research script)"}

EARNINGS = re.compile(r"(?i)(financial results|results for (the )?(first|second|third|fourth|fiscal)|quarterly results|"
                      r"reports? (record )?(revenue|results)|earnings release|fiscal \d{4} (first|second|third|fourth) quarter)")
MATERIAL = re.compile(r"(?i)(acquir|acquisition|merger|definitive agreement|agreement to|divest|appoints|names .* (chief|ceo|cfo)|"
                      r"chief executive|chief financial|resign|retire|guidance|outlook|dividend|repurchase|buyback|"
                      r"strategic partnership|export|investigation|settlement|restructur|layoff)")


def _date(s: str | None) -> str | None:
    if not s:
        return None
    try:
        return parsedate_to_datetime(s).astimezone(timezone.utc).isoformat(timespec="seconds")
    except (TypeError, ValueError):
        return s.strip()[:25]


def parse(xml_text: str) -> list[dict]:
    root = ET.fromstring(xml_text.encode("utf-8") if isinstance(xml_text, str) else xml_text)
    out = []
    for it in root.iter():
        tag = it.tag.split("}")[-1]
        if tag not in ("item", "entry"):
            continue
        children = {c.tag.split("}")[-1]: c for c in reversed(list(it))}
        t_el = children.get("title")
        title = (t_el.text or "").strip() if t_el is not None else ""
        link_el = children.get("link")
        link = ((link_el.text or "").strip() or link_el.get("href", "")) if link_el is not None else ""
        d_el = next((children[k] for k in ("pubDate", "published", "updated") if k in children), None)
        date = _date(d_el.text) if d_el is not None else None
        src = children.get("source")
        out.append({"titel": re.sub(r"\s+", " ", title), "url": link, "veroeffentlicht": date,
                    "quelle_name": (src.text or "").strip() if src is not None else None,
                    "quelle_url": src.get("url") if src is not None else None})
    return out


def fetch(url: str) -> list[dict]:
    r = requests.get(url, headers=UA, timeout=25)
    r.raise_for_status()
    return parse(r.text)


def google_news(query: str, days: int = 2) -> list[dict]:
    items = fetch(f"https://news.google.com/rss/search?q={quote_plus(query)}+when:{days}d&hl=en-US&gl=US&ceid=US:en")
    for i in items:
        i["domain"] = urlsplit(i["quelle_url"]).netloc if i.get("quelle_url") else ""
        i["titel"] = re.sub(r"\s-\s[^-]{2,60}$", "", i["titel"])   # " - Publisher" entfernen
        i["vermittler"] = "Google News RSS"
    return items


def yahoo_news(ticker: str) -> list[dict]:
    items = fetch(f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US")
    for i in items:
        i["domain"] = urlsplit(i["url"]).netloc
        i["vermittler"] = "Yahoo Finance RSS"
    return items


SCHEDULE = re.compile(r"(?i)(conference call|to host|will host|sets date|to report|will report|to announce|"
                      r"webcast|to release|will release|to present|investor day)")


def ir_importance(title: str) -> tuple[str, str]:
    if SCHEDULE.search(title) and EARNINGS.search(title):
        return "mittel", "Regel: Terminankündigung für Geschäftszahlen (enthält keine Zahlen)"
    if EARNINGS.search(title):
        return "hoch", "Regel: offizielle Mitteilung zu Geschäftszahlen"
    if MATERIAL.search(title):
        return "mittel", "Regel: offizielle Mitteilung mit wesentlichem Schlüsselwort"
    return "niedrig", "Regel: offizielle Mitteilung ohne Schlüsselwort"
