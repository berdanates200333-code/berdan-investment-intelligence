"""Nachrichten-Metadaten über die GDELT DOC 2.0 API (kostenlos, ohne Schlüssel).

GDELT indexiert weltweite Online-Nachrichten. Gespeichert werden nur Metadaten
(Titel, URL, Domain, Zeitpunkt), keine Artikeltexte. Nachrichten sind Sekundärquellen:
Sie lösen allein nie eine Meldung höchster Wichtigkeit aus.
Nutzungshinweis: GDELT-Daten sind frei nutzbar mit Quellenangabe; Abfragen höchstens alle 5 Sekunden.
"""
from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit

import requests

API = "https://api.gdeltproject.org/api/v2/doc/doc"
UA = {"User-Agent": "Mozilla/5.0 (personal research script)"}

# Grobe Zuverlässigkeitsstufen nach Herkunft (redaktionelle Wirtschaftsmedien mit Korrekturpraxis)
TIER_A = {"reuters.com", "bloomberg.com", "wsj.com", "ft.com", "apnews.com", "cnbc.com", "barrons.com",
          "economist.com", "nytimes.com", "handelsblatt.com", "faz.net", "marketwatch.com", "theinformation.com"}
TIER_B = {"techcrunch.com", "theverge.com", "arstechnica.com", "businessinsider.com", "fortune.com", "forbes.com",
          "yahoo.com", "finance.yahoo.com", "investing.com", "seekingalpha.com", "tomshardware.com",
          "anandtech.com", "zdnet.com", "venturebeat.com", "axios.com", "theregister.com", "digitimes.com"}
KEYWORDS = ["guidance", "forecast", "outlook", "export", "ban", "probe", "investigation", "lawsuit", "antitrust",
            "acquisition", "acquire", "merger", "recall", "downgrade", "upgrade", "tariff", "sanction",
            "contract", "partnership", "layoff", "resign", "ceo", "cfo", "sec ", "fine", "subpoena", "shortage",
            "delay", "supply", "order", "deal"]


def domain_tier(domain: str) -> str:
    d = domain.lower().removeprefix("www.")
    if any(d == t or d.endswith("." + t) for t in TIER_A):
        return "A (etabliertes Wirtschaftsmedium)"
    if any(d == t or d.endswith("." + t) for t in TIER_B):
        return "B (Fach-/Finanzportal)"
    return "C (unbekannt/ungeprüft)"


def normalize_url(url: str) -> str:
    p = urlsplit(url.strip())
    host = p.netloc.lower().removeprefix("www.")
    return urlunsplit(("https", host, p.path.rstrip("/"), "", ""))


def normalize_title(t: str) -> str:
    t = re.sub(r"\s[-|–]\s[^-|–]{2,40}$", "", t)   # " - Reuters" etc. abschneiden
    return re.sub(r"[^a-z0-9 ]", "", t.lower()).strip()


def search(query: str, timespan: str = "3d", maxrecords: int = 75) -> list[dict]:
    params = {"query": query, "mode": "artlist", "format": "json", "maxrecords": maxrecords,
              "timespan": timespan, "sort": "datedesc"}
    for attempt in range(3):
        r = requests.get(API, params=params, headers=UA, timeout=30)
        if r.status_code == 429:
            time.sleep(6 * (attempt + 1))
            continue
        r.raise_for_status()
        try:
            arts = r.json().get("articles", [])
        except ValueError:
            # GDELT antwortet bei Syntaxproblemen mit Text statt JSON
            raise ValueError(f"GDELT: keine JSON-Antwort ({r.text[:120]})")
        out = []
        for a in arts:
            seen = datetime.strptime(a["seendate"], "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
            out.append({"titel": a.get("title", "").strip(), "url": a["url"], "domain": a.get("domain", ""),
                        "sprache": a.get("language"), "land": a.get("sourcecountry"),
                        "gesehen_utc": seen.isoformat(timespec="seconds")})
        return out
    r.raise_for_status()
    return []


def keyword_hits(title: str) -> list[str]:
    t = f" {title.lower()} "
    return [k.strip() for k in KEYWORDS if k in t]
