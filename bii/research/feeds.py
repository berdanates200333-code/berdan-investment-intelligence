"""Unternehmens-Newsrooms (RSS/Atom) und optionale Nachrichtenaggregation (GDELT).

Es werden nur Metadaten gespeichert (Titel, Link, Datum, kurzer Anrisstext) – keine Volltexte
fremder Medien. Zuverlässigkeit:
  A  Behördliche Pflichtmitteilung (SEC-Einreichung)
  B  Offizielle Unternehmensmitteilung (eigener Newsroom/IR)
  C  Etabliertes Medium (namentlich bekannte Redaktion)
  D  Aggregator/unbekannte Herkunft – nur Hinweis, nie alleinige Grundlage
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone

from .http import Client

RELIABILITY = {
    "A": "Behördliche Pflichtveröffentlichung (SEC EDGAR) – rechtlich haftungsbewehrt, maßgeblich",
    "B": "Offizielle Unternehmensmitteilung – zuverlässig zum Inhalt, aber werblich formuliert",
    "C": "Etabliertes Nachrichtenmedium – i. d. R. geprüft, kann Fehler/Interpretationen enthalten",
    "D": "Aggregator/unbekannte Quelle – unbestätigt, nur als Hinweis",
}

# Etablierte Medien für GDELT-Treffer (Domain → C); alles andere → D
ESTABLISHED = ("reuters.com", "apnews.com", "bloomberg.com", "wsj.com", "ft.com", "cnbc.com", "nytimes.com",
               "handelsblatt.com", "faz.net", "theverge.com", "arstechnica.com", "techcrunch.com", "barrons.com")


def _iso(s: str | None) -> str | None:
    if not s:
        return None
    s = s.strip()
    try:
        return parsedate_to_datetime(s).astimezone(timezone.utc).isoformat(timespec="seconds")
    except Exception:  # noqa: BLE001
        pass
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc).isoformat(timespec="seconds")
    except Exception:  # noqa: BLE001
        m = re.match(r"(\d{4})(\d{2})(\d{2})T?(\d{2})(\d{2})(\d{2})", s)  # GDELT: 20261031T120000Z
        if m:
            y, mo, d, h, mi, se = map(int, m.groups())
            return datetime(y, mo, d, h, mi, se, tzinfo=timezone.utc).isoformat(timespec="seconds")
    return None


def _strip(html: str | None, n: int = 400) -> str:
    t = re.sub(r"<[^>]+>", " ", html or "")
    t = re.sub(r"\s+", " ", t).strip()
    return t[:n]


def parse_feed(xml_text: str) -> list[dict]:
    """RSS 2.0 und Atom. Rückgabe: [{titel, link, veroeffentlicht, anriss}]"""
    root = ET.fromstring(xml_text.encode("utf-8") if isinstance(xml_text, str) else xml_text)
    ns = {"a": "http://www.w3.org/2005/Atom"}
    items = []
    for it in root.iter("item"):
        items.append({"titel": (it.findtext("title") or "").strip(), "link": (it.findtext("link") or "").strip(),
                      "veroeffentlicht": _iso(it.findtext("pubDate") or it.findtext("{http://purl.org/dc/elements/1.1/}date")),
                      "anriss": _strip(it.findtext("description"))})
    for e in root.iter("{http://www.w3.org/2005/Atom}entry"):
        link = e.find("a:link", ns)
        items.append({"titel": (e.findtext("a:title", default="", namespaces=ns) or "").strip(),
                      "link": link.get("href") if link is not None else "",
                      "veroeffentlicht": _iso(e.findtext("a:published", namespaces=ns) or e.findtext("a:updated", namespaces=ns)),
                      "anriss": _strip(e.findtext("a:summary", namespaces=ns) or e.findtext("a:content", namespaces=ns))})
    return [i for i in items if i["titel"] and i["link"]]


def fetch_feed(client: Client, url: str, name: str) -> list[dict]:
    txt, meta = client.get(url, name, kind="text")
    items = parse_feed(txt)
    if not items:
        raise ValueError("Feed ohne Einträge oder unbekanntes Format")
    for i in items:
        i["_meta"] = meta
    return items


def gdelt(client: Client, query: str, max_records: int = 25) -> list[dict]:
    """GDELT DOC 2.0 (frei, ohne Schlüssel). Nur Metadaten; Einstufung C/D nach Domain."""
    from urllib.parse import quote
    url = (f"https://api.gdeltproject.org/api/v2/doc/doc?query={quote(query)}&mode=artlist&format=json"
           f"&maxrecords={max_records}&sort=datedesc&timespan=3d")
    data, meta = client.get(url, "GDELT DOC 2.0")
    out = []
    for a in data.get("articles", []):
        dom = (a.get("domain") or "").lower()
        out.append({"titel": a.get("title", "").strip(), "link": a.get("url", ""), "domain": dom,
                    "veroeffentlicht": _iso(a.get("seendate")), "sprache": a.get("language"),
                    "stufe": "C" if any(dom.endswith(d) for d in ESTABLISHED) else "D", "_meta": meta})
    return [o for o in out if o["titel"] and o["link"]]
