"""SEC EDGAR – offizielle, kostenfreie Primärquelle (US-Behörde, gemeinfreie Daten).

Endpunkte (https://www.sec.gov/edgar/sec-api-documentation):
- data.sec.gov/submissions/CIK##########.json   Einreichungen (Form, Datum, 8-K-Items, Dokument)
- data.sec.gov/api/xbrl/companyfacts/CIK##########.json   XBRL-Finanzdaten aus 10-K/10-Q
- www.sec.gov/Archives/edgar/data/<cik>/<acc>/index.json   Dateien einer Einreichung
Nutzungsbedingungen: deklarierter User-Agent, höchstens 10 Anfragen/Sekunde, kein übermäßiger Abruf.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser

from .http import Client

SOURCE_SUBMISSIONS = "SEC EDGAR Submissions"
SOURCE_FACTS = "SEC EDGAR XBRL companyfacts"
SOURCE_ARCHIVE = "SEC EDGAR Archiv"

# Wichtigkeit von 8-K-Items (Regel, keine KI). Quelle der Item-Bedeutungen: SEC Form 8-K General Instructions.
ITEMS_8K = {
    "1.01": ("Wesentlicher Vertrag abgeschlossen", 0.70),
    "1.02": ("Wesentlicher Vertrag beendet", 0.70),
    "1.03": ("Insolvenz/Zwangsverwaltung", 1.00),
    "1.05": ("Wesentlicher Cybersicherheitsvorfall", 0.85),
    "2.01": ("Erwerb/Veräußerung von Vermögenswerten abgeschlossen", 0.80),
    "2.02": ("Geschäftsergebnisse (Quartals-/Jahreszahlen)", 0.90),
    "2.03": ("Neue wesentliche Finanzverbindlichkeit", 0.60),
    "2.04": ("Auslöser für beschleunigte Verbindlichkeit", 0.85),
    "2.05": ("Restrukturierungs-/Ausstiegskosten", 0.75),
    "2.06": ("Wesentliche Wertminderung", 0.80),
    "3.01": ("Delisting/Börsenregel-Verstoß", 0.90),
    "3.02": ("Nicht registrierter Aktienverkauf", 0.50),
    "3.03": ("Änderung von Aktionärsrechten", 0.50),
    "4.01": ("Wechsel des Abschlussprüfers", 0.75),
    "4.02": ("Frühere Abschlüsse nicht mehr verlässlich", 1.00),
    "5.01": ("Kontrollwechsel", 0.90),
    "5.02": ("Wechsel in Vorstand/Aufsichtsrat bzw. Vergütung", 0.65),
    "5.03": ("Satzungsänderung/Geschäftsjahr", 0.30),
    "5.07": ("Abstimmungsergebnisse Hauptversammlung", 0.25),
    "7.01": ("Regulation-FD-Mitteilung", 0.40),
    "8.01": ("Sonstige Ereignisse", 0.45),
    "9.01": ("Anhänge/Exhibits", 0.05),
}
FORM_WEIGHT = {
    "10-K": 0.80, "10-Q": 0.70, "8-K": None, "DEF 14A": 0.30, "S-3": 0.50, "S-3ASR": 0.50, "424B2": 0.35,
    "424B5": 0.45, "SC 13D": 0.60, "SC 13D/A": 0.50, "SC 13G": 0.25, "SC 13G/A": 0.20, "4": 0.15, "144": 0.15,
    "11-K": 0.10, "S-8": 0.20, "10-K/A": 0.75, "10-Q/A": 0.65, "8-K/A": 0.50,
}


def cik10(cik: str | int) -> str:
    return str(int(cik)).zfill(10)


def submissions(client: Client, cik: str) -> dict:
    data, meta = client.get(f"https://data.sec.gov/submissions/CIK{cik10(cik)}.json", SOURCE_SUBMISSIONS)
    data["_meta"] = meta
    return data


def recent_filings(sub: dict) -> list[dict]:
    """Spaltenweise 'recent'-Tabelle in eine Liste von Einreichungen umwandeln."""
    r = sub.get("filings", {}).get("recent", {})
    keys = list(r.keys())
    n = len(r.get("accessionNumber", []))
    out = []
    cik = int(sub["cik"])
    for i in range(n):
        f = {k: r[k][i] for k in keys}
        acc = f["accessionNumber"]
        f["cik"] = cik
        f["filing_url"] = archive_url(cik, acc, f.get("primaryDocument") or "")
        f["index_url"] = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace('-', '')}/{acc}-index.htm"
        out.append(f)
    return out


def archive_url(cik: int | str, accession: str, filename: str = "") -> str:
    return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}/{filename}"


def filing_importance(f: dict) -> tuple[float, list[str]]:
    """Regelbasierte Wichtigkeit einer Einreichung (0..1) samt Begründung."""
    form = f.get("form", "")
    if form in ("8-K", "8-K/A"):
        items = [i.strip() for i in (f.get("items") or "").split(",") if i.strip()]
        scored = [(ITEMS_8K.get(i, ("Item " + i, 0.4))) for i in items] or [("8-K ohne Item-Angabe", 0.4)]
        score = max(s for _, s in scored)
        if form == "8-K/A":
            score = min(score, 0.6)
        return score, [f"8-K Item {i}: {ITEMS_8K.get(i, ('unbekannt', 0))[0]}" for i in items]
    w = FORM_WEIGHT.get(form)
    if w is None:
        return 0.10, [f"Formular {form}"]
    return w, [f"Formular {form}"]


def company_facts(client: Client, cik: str) -> dict:
    data, meta = client.get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik10(cik)}.json", SOURCE_FACTS)
    data["_meta"] = meta
    return data


def filing_index(client: Client, cik: int | str, accession: str) -> list[dict]:
    data, _ = client.get(archive_url(cik, accession, "index.json"), SOURCE_ARCHIVE)
    return data.get("directory", {}).get("item", [])


def pick_press_release(items: list[dict]) -> str | None:
    """Exhibit 99.1 (Pressemitteilung) in einer 8-K-Einreichung finden."""
    names = [i.get("name", "") for i in items]
    for pat in (r"ex-?99[._-]?0?1\b", r"ex99[-_]?1", r"ex-?99", r"exhibit99"):
        for n in names:
            if re.search(pat, n.lower()) and n.lower().endswith((".htm", ".html", ".txt")):
                return n
    return None


class _Text(HTMLParser):
    SKIP = {"script", "style", "head", "title"}
    BLOCK = {"p", "div", "br", "tr", "li", "h1", "h2", "h3", "h4", "table", "section"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        if tag in self.BLOCK:
            self.out.append("\n")
        if tag in ("td", "th"):
            self.out.append(" | ")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1
        if tag in self.BLOCK:
            self.out.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.out.append(data)


def html_to_text(html: str) -> str:
    p = _Text()
    p.feed(html)
    txt = "".join(p.out).replace("\xa0", " ")
    txt = re.sub(r"[ \t]+", " ", txt)
    txt = re.sub(r"\n\s*\n\s*(\n\s*)+", "\n\n", txt)
    # XBRL-Kopfzeilen (ix:header) erzeugen oft Rauschen am Anfang – Zeilen ohne Buchstaben entfernen
    lines = [ln.strip() for ln in txt.splitlines()]
    return "\n".join(ln for ln in lines if re.search(r"[A-Za-z]", ln) or not ln).strip()
