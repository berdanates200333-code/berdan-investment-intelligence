"""Ereignisse: Klassifizierung (Python-Regeln), Zuverlässigkeit, Dubletten, append-only Speicher.

Wichtig: Alles hier sind deterministische REGELN, keine KI-Bewertung. Die Wichtigkeit entscheidet
nur, ob ein Ereignis zur KI-Analyse vorgemerkt und ob benachrichtigt wird.
"""
from __future__ import annotations

import difflib
import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .. import journal
from . import news as newsmod

ROOT = Path(__file__).resolve().parents[2]
EVENTS = ROOT / "research" / "db" / "events.jsonl"

# 8-K-Items laut SEC Form 8-K (Kurzbezeichnung, Wichtigkeit)
ITEMS_8K = {
    "1.01": ("Wesentlicher Vertrag abgeschlossen", "mittel"),
    "1.02": ("Wesentlicher Vertrag beendet", "mittel"),
    "1.03": ("Insolvenz/Zwangsverwaltung", "hoch"),
    "1.05": ("Wesentlicher Cybersicherheitsvorfall", "hoch"),
    "2.01": ("Übernahme/Veräußerung abgeschlossen", "hoch"),
    "2.02": ("Geschäftszahlen (Results of Operations)", "hoch"),
    "2.03": ("Neue wesentliche Finanzverbindlichkeit", "mittel"),
    "2.04": ("Auslöser für vorzeitige Fälligkeit", "hoch"),
    "2.05": ("Restrukturierung/Ausstiegskosten", "hoch"),
    "2.06": ("Wesentliche Wertminderung", "hoch"),
    "3.01": ("Börsennotierung gefährdet/Delisting", "hoch"),
    "3.02": ("Nicht registrierte Aktienausgabe", "mittel"),
    "3.03": ("Änderung der Aktionärsrechte", "mittel"),
    "4.01": ("Wechsel des Abschlussprüfers", "mittel"),
    "4.02": ("Frühere Abschlüsse nicht mehr verlässlich", "hoch"),
    "5.01": ("Kontrollwechsel", "hoch"),
    "5.02": ("Wechsel im Management/Vorstand", "mittel"),
    "5.03": ("Satzungsänderung/Geschäftsjahr", "niedrig"),
    "5.07": ("Ergebnisse der Hauptversammlung", "niedrig"),
    "7.01": ("Regulation-FD-Mitteilung", "niedrig"),
    "8.01": ("Sonstige Ereignisse", "mittel"),
    "9.01": ("Anlagen/Finanzangaben", None),
}
FORMS = {
    "10-K": ("Jahresbericht", "hoch"), "10-K/A": ("Jahresbericht (Korrektur)", "mittel"),
    "10-Q": ("Quartalsbericht", "hoch"), "10-Q/A": ("Quartalsbericht (Korrektur)", "mittel"),
    "SC 13D": ("Beteiligung >5 % (aktiv)", "mittel"), "SCHEDULE 13D": ("Beteiligung >5 % (aktiv)", "mittel"),
    "SC 13G": ("Beteiligung >5 % (passiv)", "niedrig"), "SCHEDULE 13G": ("Beteiligung >5 % (passiv)", "niedrig"),
    "S-3": ("Registrierung Wertpapieremission", "mittel"), "S-3ASR": ("Registrierung Wertpapieremission", "mittel"),
    "S-4": ("Registrierung (Fusion/Tausch)", "hoch"), "DEF 14A": ("Einladung Hauptversammlung", "niedrig"),
    "4": ("Insider-Transaktion", "niedrig"), "144": ("Geplanter Insider-Verkauf", "niedrig"),
    "SD": ("Konfliktmineralien-Bericht", "niedrig"), "11-K": ("Mitarbeiterplan-Bericht", "niedrig"),
}
RANK = {"hoch": 3, "mittel": 2, "niedrig": 1, None: 0}


def classify_filing(form: str, items: str) -> tuple[str, str, str]:
    """-> (Bezeichnung, Wichtigkeit, Begründung der Regel)"""
    if form in ("8-K", "8-K/A"):
        found = [(i, *ITEMS_8K.get(i, (f"Item {i}", "mittel"))) for i in [x.strip() for x in (items or "").split(",") if x.strip()]]
        found = [f for f in found if f[2]]
        if not found:
            return "8-K (ohne einordenbares Item)", "niedrig", "Regel: 8-K ohne bewertbares Item"
        top = max(found, key=lambda f: RANK[f[2]])
        label = "8-K: " + "; ".join(f"{i} {t}" for i, t, _ in found)
        return label, top[2], f"Regel: höchstes 8-K-Item {top[0]} ({top[1]}) -> {top[2]}"
    if form.startswith("424B"):
        return "Emissionsprospekt (424B)", "mittel", "Regel: Prospekt -> mögliche Verwässerung/Fremdkapital"
    label, imp = FORMS.get(form, (form, "niedrig"))
    return label, imp, f"Regel: Formular {form} -> {imp}"


def news_importance(title: str, tier: str) -> tuple[str, str]:
    hits = newsmod.keyword_hits(title)
    if hits and tier.startswith("A"):
        return "mittel", f"Regel: Schlüsselwörter {hits} in etabliertem Medium"
    return "niedrig", (f"Regel: Schlüsselwörter {hits}, aber Quelle {tier[0]}" if hits else "Regel: Nachricht ohne Schlüsselwort")


def event_id(kind: str, ticker: str, key: str) -> str:
    if kind == "news":
        key = hashlib.sha1(newsmod.normalize_url(key).encode()).hexdigest()[:16]
    return f"{kind}:{ticker}:{key}"


class Store:
    """Append-only Ereignisspeicher (Hash-Kette wie das FT1-Journal)."""

    def __init__(self, path: Path = EVENTS):
        self.path = path
        self.entries = journal.read(path)
        self.ids = {e["id"] for e in self.entries if e.get("typ") == "ereignis"}
        self.recent_titles = [(e["ticker"], newsmod.normalize_title(e["titel"]), e.get("erfasst_utc") or e["erstellt_utc"], e["id"])
                              for e in self.entries if e.get("typ") == "ereignis" and e.get("art") == "news"]

    def is_duplicate_news(self, ticker: str, title: str, now: datetime, days: int = 7) -> str | None:
        nt = newsmod.normalize_title(title)
        if len(nt) < 12:
            return None
        cutoff = (now - timedelta(days=days)).isoformat()
        for t, other, ts, eid in self.recent_titles:
            if t == ticker and ts >= cutoff and difflib.SequenceMatcher(None, nt, other).ratio() >= 0.88:
                return eid
        return None

    def add(self, ev: dict, now: datetime | None = None) -> dict | None:
        if ev["id"] in self.ids:
            return None
        e = journal.append({"typ": "ereignis", **ev}, self.path, now=now)
        self.entries.append(e)
        self.ids.add(ev["id"])
        if ev.get("art") == "news":
            self.recent_titles.append((ev["ticker"], newsmod.normalize_title(ev["titel"]), e.get("erfasst_utc") or e["erstellt_utc"], ev["id"]))
        return e

    def set_status(self, event_id_: str, status: str, note: str = "", now: datetime | None = None) -> dict:
        return journal.append({"typ": "status", "id": f"status:{event_id_}:{status}", "bezug": event_id_,
                               "status": status, "notiz": note}, self.path, now=now)

    def status_of(self, event_id_: str) -> str | None:
        st = [e for e in self.entries if e.get("typ") == "status" and e.get("bezug") == event_id_]
        return st[-1]["status"] if st else None

    def events(self, ticker: str | None = None, since: str | None = None) -> list[dict]:
        out = [e for e in self.entries if e.get("typ") == "ereignis"]
        if ticker:
            out = [e for e in out if e["ticker"] == ticker]
        if since:
            out = [e for e in out if (e.get("veroeffentlicht") or e.get("erfasst_utc") or e["erstellt_utc"]) >= since]
        return out


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
