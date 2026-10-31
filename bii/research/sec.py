"""SEC-EDGAR-Client (kostenlos, offiziell, ohne API-Schlüssel).

Nutzungsbedingungen (sec.gov/os/accessing-edgar-data): höchstens 10 Anfragen/Sekunde und ein
User-Agent mit Kontaktangabe. Der User-Agent kommt aus der Umgebungsvariable SEC_USER_AGENT
(GitHub-Repository-Variable, kein Geheimnis). Ohne Variable wird eine neutrale Projektkennung genutzt.
"""
from __future__ import annotations

import html
import os
import re
import time

import requests

DEFAULT_UA = "berdan-investment-intelligence research (berdanates200333-code@users.noreply.github.com)"
MIN_INTERVAL = 0.15   # ~6-7 Anfragen/Sekunde, unter dem SEC-Limit von 10
_last = [0.0]


def _get(url: str, timeout: int = 30) -> requests.Response:
    wait = MIN_INTERVAL - (time.monotonic() - _last[0])
    if wait > 0:
        time.sleep(wait)
    headers = {"User-Agent": os.environ.get("SEC_USER_AGENT") or DEFAULT_UA, "Accept-Encoding": "gzip, deflate"}
    for attempt in range(3):
        _last[0] = time.monotonic()
        r = requests.get(url, headers=headers, timeout=timeout)
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(2 ** attempt)
            continue
        r.raise_for_status()
        return r
    r.raise_for_status()
    return r


def cik10(cik: str | int) -> str:
    return str(int(cik)).zfill(10)


def submissions(cik) -> dict:
    return _get(f"https://data.sec.gov/submissions/CIK{cik10(cik)}.json").json()


def companyfacts(cik) -> dict:
    return _get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik10(cik)}.json").json()


def recent_filings(sub: dict) -> list[dict]:
    """Liste der jüngsten Einreichungen aus dem submissions-JSON (neueste zuerst)."""
    r = sub["filings"]["recent"]
    keys = ["accessionNumber", "filingDate", "acceptanceDateTime", "form", "items", "primaryDocument",
            "primaryDocDescription", "reportDate"]
    n = len(r["accessionNumber"])
    return [{k: (r.get(k) or [""] * n)[i] for k in keys} for i in range(n)]


def filing_base(cik, accession: str) -> str:
    return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}"


def filing_url(cik, f: dict) -> str:
    return f"{filing_base(cik, f['accessionNumber'])}/{f['primaryDocument']}"


def filing_index(cik, accession: str) -> list[dict]:
    j = _get(f"{filing_base(cik, accession)}/index.json").json()
    return j.get("directory", {}).get("item", [])


def html_to_text(raw: str) -> str:
    raw = re.sub(r"(?is)<ix:header>.*?</ix:header>", " ", raw)
    raw = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", raw)
    raw = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>|</h\d>", "\n", raw)
    txt = html.unescape(re.sub(r"(?s)<[^>]+>", " ", raw))
    txt = re.sub(r"[ \t\xa0]+", " ", txt)
    return re.sub(r"\n\s*\n+", "\n\n", txt).strip()


def fetch_text(url: str, limit: int | None = None) -> str:
    t = html_to_text(_get(url, timeout=60).text)
    return t[:limit] if limit else t


def press_release_url(cik, accession: str, primary: str) -> str | None:
    """Exhibit 99.x (Pressemitteilung) eines 8-K finden."""
    items = filing_index(cik, accession)
    names = [i["name"] for i in items if i["name"].lower().endswith((".htm", ".html")) and i["name"] != primary]
    ex = [n for n in names if re.search(r"ex[-_]?99|exhibit[-_]?99|ex991|99[-_]?1", n.lower())]
    pick = ex[0] if ex else None
    return f"{filing_base(cik, accession)}/{pick}" if pick else None


def xbrl_instance_url(cik, accession: str) -> str | None:
    """Von EDGAR extrahierte XBRL-Instanz (*_htm.xml) einer Inline-XBRL-Einreichung."""
    items = filing_index(cik, accession)
    cands = [i["name"] for i in items if i["name"].endswith("_htm.xml")]
    if not cands:
        cands = [i["name"] for i in items if re.search(r"\d{8}\.xml$", i["name"]) and "_" not in i["name"]]
    return f"{filing_base(cik, accession)}/{cands[0]}" if cands else None


def get_raw(url: str) -> bytes:
    return _get(url, timeout=60).content
