"""Fortschreibbare Research-Datenbank (Git-freundliche Dateien statt Binär-DB).

research/desk/desk/universe.json                beobachtete Unternehmen (erweiterbar)
research/desk/companies/<TICKER>/profile.json  qualitatives Profil (Geschäftsmodell, Segmente, Management …)
                                          – jedes Feld mit Quelle und Stand
research/desk/companies/<TICKER>/financials.json  zuletzt berechnete XBRL-Kennzahlen (überschrieben,
                                          Historie über Git und über Erkenntnisse 'neue_zahlen')
research/desk/findings.jsonl                 Erkenntnisse, append-only, Hash-Kette (wie FT1-Journal)
research/desk/evidence/<id>.txt              gespeicherte Belegtexte offizieller Quellen (für KI-Analysen)
research/desk/queue/<id>.json                Analyseaufträge für Claude (KI)
research/desk/state/monitor_status.json      Betriebszustand, Fehlerzähler je Quelle und Ursache

Warum Dateien statt SQLite: Der Monitor läuft in GitHub Actions ohne dauerhaften Speicher; der Zustand
wird ins Repository geschrieben. Textdateien sind dort prüfbar (Diff), zusammenführbar und versioniert.
Für deutlich mehr Unternehmen (Hunderte) bleibt die Struktur gleich (ein Ordner je Unternehmen);
findings.jsonl lässt sich bei Bedarf jahresweise aufteilen.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from .. import journal as chain

ROOT = Path(__file__).resolve().parents[2]
R = ROOT / "research" / "desk"
FINDINGS = R / "findings.jsonl"
EVIDENCE = R / "evidence"
QUEUE = R / "queue"
STATE = R / "state" / "monitor_status.json"


def load_universe(path: Path | None = None) -> list[dict]:
    return json.loads((path or R / "universe.json").read_text())


def company_dir(ticker: str) -> Path:
    d = R / "companies" / ticker
    d.mkdir(parents=True, exist_ok=True)
    return d


def read_json(p: Path, default=None):
    return json.loads(p.read_text()) if p.exists() else default


def write_json(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=False) + "\n")


# ---------------------------------------------------------------- Erkenntnisse (append-only)
def findings(path: Path | None = None) -> list[dict]:
    # Pfad erst beim Aufruf auflösen (nicht beim Import), damit Tests/Konfiguration greifen
    return chain.read(path or FINDINGS)


def norm_url(u: str) -> str:
    u = (u or "").strip().lower()
    u = re.sub(r"^https?://(www\.)?", "", u)
    u = re.sub(r"[?#].*$", "", u)
    return u.rstrip("/")


def norm_title(t: str) -> list[str]:
    stop = {"the", "a", "an", "of", "to", "and", "for", "in", "on", "with", "its", "at", "by", "from", "as"}
    return [w for w in re.findall(r"[a-z0-9]+", (t or "").lower()) if w not in stop]


def jaccard(a: list[str], b: list[str]) -> float:
    sa, sb = set(a), set(b)
    return len(sa & sb) / len(sa | sb) if sa and sb else 0.0


def dedupe_key(kind: str, value: str) -> str:
    return f"{kind}:{value}"


def finding_id(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()[:16]


class Index:
    """Schneller Dublettenabgleich gegen alle bisherigen Erkenntnisse."""

    def __init__(self, items: list[dict]):
        self.keys = {i["dedupe_key"] for i in items if i.get("dedupe_key")}
        self.urls = {norm_url(i["quelle"]["url"]) for i in items if i.get("quelle", {}).get("url")}
        self.titles = [(i.get("tickers", []), norm_title(i.get("titel", "")), (i.get("veroeffentlicht") or "")[:10], i["id"])
                       for i in items if i.get("typ") in ("pressemitteilung", "nachricht")]

    def duplicate_of(self, key: str, url: str | None, title: str | None, tickers: list[str], day: str | None,
                     threshold: float = 0.8) -> str | None:
        if key in self.keys:
            return "gleicher Schlüssel"
        if url and norm_url(url) in self.urls:
            return "gleiche URL"
        if title:
            nt = norm_title(title)
            for tk, t, d, fid in self.titles:
                if set(tk) & set(tickers) and d and day and abs(_days(d, day)) <= 3 and jaccard(nt, t) >= threshold:
                    return f"nahezu gleicher Titel wie {fid}"
        return None

    def add(self, f: dict) -> None:
        self.keys.add(f["dedupe_key"])
        if f.get("quelle", {}).get("url"):
            self.urls.add(norm_url(f["quelle"]["url"]))
        if f.get("typ") in ("pressemitteilung", "nachricht"):
            self.titles.append((f.get("tickers", []), norm_title(f.get("titel", "")), (f.get("veroeffentlicht") or "")[:10], f["id"]))


def _days(a: str, b: str) -> int:
    from datetime import date
    return (date.fromisoformat(a) - date.fromisoformat(b)).days


def append_finding(f: dict, path: Path | None = None) -> dict:
    return chain.append({"typ_eintrag": "erkenntnis", **f}, path=path or FINDINGS)


def verify_findings(path: Path | None = None) -> tuple[bool, str]:
    return chain.verify(path or FINDINGS)


def save_evidence(fid: str, text: str, meta: dict, limit: int = 250_000) -> str:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    p = EVIDENCE / f"{fid}.txt"
    head = (f"QUELLE: {meta.get('url')}\nABGERUFEN_UTC: {meta.get('abgerufen_utc')}\nSHA256_ORIGINAL: {meta.get('sha256')}\n"
            f"HINWEIS: Automatisch aus HTML extrahierter Text, ggf. gekürzt auf {limit} Zeichen.\n\n")
    p.write_text(head + text[:limit])
    return str(p.relative_to(ROOT))
