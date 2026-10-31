"""Research-Monitor: periodische Unternehmens- und Nachrichtenüberwachung (Python-Regeln, keine KI).

Aufruf:  python scripts/research_monitor.py [--tickers NVDA,AMD] [--ohne-nachrichten]
Schreibt:
  research/desk/findings.jsonl                neue Erkenntnisse (append-only, Hash-Kette, Dubletten gefiltert)
  research/desk/companies/<T>/financials.json Kennzahlen aus SEC-XBRL
  research/desk/companies/<T>/valuation.json  Kurs, Multiplikatoren, Reverse-DCF, Thesen-Prüfung
  research/desk/evidence/<id>.txt             Belegtexte offizieller Quellen
  research/desk/queue/<id>.json               Analyseaufträge für Claude (Wichtigkeit ≥ Schwelle)
  research/desk/reports/latest.md (+ Datum)   nachvollziehbarer Bericht
  research/desk/state/monitor_status.json     Lauf, Heartbeat, Fehlerzähler je Quelle und Ursache
  research/desk/alert.txt                     nur wenn eine Benachrichtigung nötig ist (nicht versioniert)
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bii.research import feeds, financials, sec, store, thesis, valuation  # noqa: E402
from bii.research.http import Client, FetchError, FetchLog, now_utc  # noqa: E402
from bii.research.report import write_report  # noqa: E402

QUEUE_THRESHOLD = 0.70     # ab hier wird eine KI-Analyse angefordert
ALERT_THRESHOLD = 0.85     # ab hier Push-Benachrichtigung (gebündelt, max. 1 je Lauf)
BASELINE_DAYS = 120        # Erstlauf: Einreichungen der letzten 120 Tage als Ausgangsbasis
EVIDENCE_FORMS = {"10-K", "10-Q"}


class Run:
    def __init__(self, tickers: list[str] | None, news: bool):
        self.log = FetchLog()
        self.client = Client(self.log)
        self.universe = [c for c in store.load_universe() if not tickers or c["ticker"] in tickers]
        self.items = store.findings()
        self.index = store.Index(self.items)
        self.new: list[dict] = []
        self.skipped: list[dict] = []
        self.news = news
        self.status = store.read_json(store.STATE, {}) or {}
        self.status.setdefault("fehlerzaehler", {})
        self.results: dict = {}
        # Erstlauf je Unternehmen: Analysen ja (jüngste Pflichtberichte), Push-Benachrichtigungen nein
        self.first_run = {c["ticker"]: not any(c["ticker"] in i.get("tickers", []) for i in self.items) for c in self.universe}

    # ---------------------------------------------------------------- Erkenntnis anlegen
    def add(self, *, key: str, typ: str, ticker: str, titel: str, quelle: dict, stufe: str, veroeffentlicht: str | None,
            wichtigkeit: float, gruende: list[str], inhalt: dict | None = None, baseline: bool = False,
            evidenz: str | None = None) -> dict | None:
        dup = self.index.duplicate_of(key, quelle.get("url"), titel if typ in ("pressemitteilung", "nachricht") else None,
                                      [ticker], (veroeffentlicht or "")[:10] or None)
        if dup:
            self.skipped.append({"ticker": ticker, "titel": titel[:90], "grund": dup})
            return None
        fid = store.finding_id(key)
        f = {"id": fid, "dedupe_key": key, "typ": typ, "tickers": [ticker], "titel": titel, "quelle": quelle,
             "zuverlaessigkeit": {"stufe": stufe, "bedeutung": feeds.RELIABILITY[stufe]},
             "veroeffentlicht": veroeffentlicht, "wichtigkeit": {"wert": round(wichtigkeit, 2), "gruende": gruende,
                                                                 "methode": "Python-Regel"},
             "inhalt": inhalt or {}, "erstlauf_basis": baseline, "erstlauf": self.first_run.get(ticker, False),
             "evidenz": evidenz, "bezug": [],
             "analyse": {"status": "angefordert" if wichtigkeit >= QUEUE_THRESHOLD else "nicht_noetig"}}
        self.new.append(f)
        self.index.add(f)
        return f

    def count_error(self, source: str, cause: str | None) -> None:
        """Fehlerzähler je Quelle UND Ursache; Erfolg setzt alle Ursachen dieser Quelle zurück."""
        fz = self.status["fehlerzaehler"]
        if cause is None:
            for k in [k for k in fz if k.startswith(source + "|")]:
                fz[k]["folge"] = 0
            return
        e = fz.setdefault(f"{source}|{cause}", {"folge": 0, "gesamt": 0, "erstmals": now_utc()})
        e["folge"] += 1
        e["gesamt"] += 1
        e["zuletzt"] = now_utc()

    # ---------------------------------------------------------------- SEC
    def sec_filings(self, c: dict) -> None:
        t = c["ticker"]
        src = f"SEC Submissions {t}"
        try:
            sub = sec.submissions(self.client, c["cik"])
            self.count_error(src, None)
        except FetchError as e:
            self.count_error(src, e.cause)
            return
        first = not any(t in i.get("tickers", []) and i["typ"] == "einreichung" for i in self.items)
        cutoff = (date.today() - timedelta(days=BASELINE_DAYS)).isoformat()
        filings = [f for f in sec.recent_filings(sub) if f["filingDate"] >= cutoff] if first else sec.recent_filings(sub)[:60]
        # Erstlauf: nur die jüngsten Pflichtberichte werden analysiert, der Rest dient als Basis
        latest_needed = {}
        for f in filings:
            tag = "2.02" if f["form"] == "8-K" and "2.02" in (f.get("items") or "") else f["form"]
            latest_needed.setdefault(tag, f["accessionNumber"])
        for f in sorted(filings, key=lambda x: (x["filingDate"], x["accessionNumber"])):
            score, why = sec.filing_importance(f)
            baseline = first and f["accessionNumber"] not in {latest_needed.get(k) for k in ("10-K", "10-Q", "2.02")}
            if baseline:
                score = min(score, QUEUE_THRESHOLD - 0.01)
                why = why + ["Erstlauf: als Ausgangsbasis erfasst, keine Analyse ausgelöst"]
            items = f.get("items") or ""
            titel = f"{f['form']}{' Items ' + items if items else ''}: {f.get('primaryDocDescription') or f.get('primaryDocument')}"
            fnd = self.add(key=store.dedupe_key("sec", f["accessionNumber"]), typ="einreichung", ticker=t, titel=titel,
                           quelle={"name": "SEC EDGAR", "url": f["filing_url"], "index": f["index_url"],
                                   "accession": f["accessionNumber"], "abgerufen_utc": sub["_meta"]["abgerufen_utc"]},
                           stufe="A", veroeffentlicht=f.get("acceptanceDateTime") or f["filingDate"], wichtigkeit=score,
                           gruende=why, baseline=baseline,
                           inhalt={"formular": f["form"], "items": items, "berichtszeitraum": f.get("reportDate"),
                                   "eingereicht": f["filingDate"]})
            if fnd and score >= QUEUE_THRESHOLD:
                self.evidence(c, f, fnd)

    def evidence(self, c: dict, f: dict, fnd: dict) -> None:
        """Belegtext sichern: bei 8-K die Pressemitteilung (Exhibit 99.1), bei 10-K/10-Q das Hauptdokument."""
        src = f"SEC Archiv {c['ticker']}"
        try:
            doc = f.get("primaryDocument")
            if f["form"].startswith("8-K"):
                ex = sec.pick_press_release(sec.filing_index(self.client, c["cik"], f["accessionNumber"]))
                doc = ex or doc
            if not doc:
                return
            url = sec.archive_url(c["cik"], f["accessionNumber"], doc)
            html, meta = self.client.get(url, src, kind="text")
            fnd["evidenz"] = store.save_evidence(fnd["id"], sec.html_to_text(html), meta,
                                                 limit=400_000 if f["form"] in EVIDENCE_FORMS else 120_000)
            fnd["quelle"]["dokument"] = url
            self.count_error(src, None)
        except FetchError as e:
            self.count_error(src, e.cause)

    def sec_financials(self, c: dict) -> dict | None:
        t = c["ticker"]
        src = f"SEC XBRL {t}"
        try:
            facts = sec.company_facts(self.client, c["cik"])
            self.count_error(src, None)
        except FetchError as e:
            self.count_error(src, e.cause)
            return store.read_json(store.company_dir(t) / "financials.json")
        fin = financials.build(facts)
        p = store.company_dir(t) / "financials.json"
        old = store.read_json(p)
        k = fin["kennzahlen"]
        old_last = (old or {}).get("kennzahlen", {}).get("letztes_quartal")
        if k.get("letztes_quartal") and k["letztes_quartal"] != old_last:
            g, gm = k.get("umsatzwachstum_yoy_q"), k.get("bruttomarge_q")
            reasons = [f"neues Quartal {k['letztes_quartal']} in XBRL-Daten"]
            score = 0.80 if old else 0.60
            if old:
                og = old["kennzahlen"].get("umsatzwachstum_yoy_q")
                ogm = old["kennzahlen"].get("bruttomarge_q")
                if g is not None and og is not None and abs(g - og) >= 0.10:
                    reasons.append(f"Umsatzwachstum ändert sich um {(g - og) * 100:+.0f} Prozentpunkte")
                    score = 0.90
                if gm is not None and ogm is not None and abs(gm - ogm) >= 0.03:
                    reasons.append(f"Bruttomarge ändert sich um {(gm - ogm) * 100:+.1f} Prozentpunkte")
                    score = max(score, 0.85)
            last_rev = fin["flow"]["umsatz"][-1]
            self.add(key=store.dedupe_key("xbrl", f"{t}:{k['letztes_quartal']}"), typ="neue_zahlen", ticker=t,
                     titel=f"{t}: Quartalszahlen bis {k['letztes_quartal']} (XBRL)",
                     quelle={"name": "SEC EDGAR XBRL companyfacts", "url": facts["_meta"]["url"],
                             "accession": last_rev["accn"], "abgerufen_utc": facts["_meta"]["abgerufen_utc"]},
                     stufe="A", veroeffentlicht=last_rev["eingereicht"], wichtigkeit=score, gruende=reasons,
                     baseline=not old,
                     inhalt={"umsatz_q": k.get("umsatz_q"), "umsatzwachstum_yoy_q": g, "bruttomarge_q": gm,
                             "operative_marge_q": k.get("operative_marge_q"), "fcf_ttm": k.get("fcf_ttm")})
        known = {(x["konzept"], x["ende"], x["neu_accn"]) for x in (old or {}).get("korrekturen", [])}
        for r in fin["korrekturen"]:
            if old and (r["konzept"], r["ende"], r["neu_accn"]) not in known:
                self.add(key=store.dedupe_key("korrektur", f"{t}:{r['konzept']}:{r['ende']}:{r['neu_accn']}"),
                         typ="korrektur", ticker=t, titel=f"{t}: geänderter Wert {r['konzept']} für Zeitraum bis {r['ende']}",
                         quelle={"name": "SEC EDGAR XBRL", "url": facts["_meta"]["url"], "accession": r["neu_accn"]},
                         stufe="A", veroeffentlicht=r["neu_eingereicht"], wichtigkeit=0.75,
                         gruende=["Wert in späterer Einreichung um >0,5 % geändert"], inhalt=r)
        store.write_json(p, fin)
        return fin

    # ---------------------------------------------------------------- Newsrooms / Nachrichten
    def newsroom(self, c: dict) -> None:
        # Erstlauf je Unternehmen (nicht je Feed) – sonst lösen ältere Meldungen aus Feed 2 Alarme aus
        first = not any(c["ticker"] in i.get("tickers", []) and i["typ"] == "pressemitteilung" for i in self.items)
        for feed in c.get("ir_feeds", []):
            src = f"Newsroom {feed['name']}"
            try:
                items = feeds.fetch_feed(self.client, feed["url"], src)
                self.count_error(src, None)
            except FetchError as e:
                self.count_error(src, e.cause)
                continue
            except Exception as e:  # noqa: BLE001 – Formatfehler
                self.count_error(src, "format")
                self.log.add(url=feed["url"], quelle=src, ok=False, ursache="format", detail=str(e)[:160])
                continue
            for it in items[:30]:
                score, why = press_importance(it["titel"])
                self.add(key=store.dedupe_key("url", store.norm_url(it["link"])), typ="pressemitteilung", ticker=c["ticker"],
                         titel=it["titel"], quelle={"name": feed["name"], "url": it["link"], "feed": feed["url"],
                                                    "abgerufen_utc": it["_meta"]["abgerufen_utc"]},
                         stufe="B", veroeffentlicht=it["veroeffentlicht"],
                         wichtigkeit=min(score, QUEUE_THRESHOLD - 0.01) if first else score,
                         gruende=why + (["Erstlauf: Ausgangsbasis"] if first else []), baseline=first,
                         inhalt={"anriss": it["anriss"]})

    def gdelt(self, c: dict) -> None:
        q = c.get("nachrichten_suche")
        if not q:
            return
        src = "GDELT"
        try:
            arts = feeds.gdelt(self.client, q)
            self.count_error(src, None)
        except FetchError as e:
            self.count_error(src, e.cause)
            return
        for a in arts[:15]:
            if a.get("sprache") not in (None, "English", "German"):
                continue
            # Medienberichte lösen allein nie eine Analyse aus (Stufe C/D)
            self.add(key=store.dedupe_key("url", store.norm_url(a["link"])), typ="nachricht", ticker=c["ticker"],
                     titel=a["titel"], quelle={"name": a["domain"], "url": a["link"], "via": "GDELT DOC 2.0",
                                               "abgerufen_utc": a["_meta"]["abgerufen_utc"]},
                     stufe=a["stufe"], veroeffentlicht=a["veroeffentlicht"], wichtigkeit=0.2,
                     gruende=["Medienbericht – nur Hinweis, löst allein keine Analyse aus"])

    # ---------------------------------------------------------------- Bewertung + Thesen
    def valuate(self, c: dict, fin: dict | None) -> None:
        t = c["ticker"]
        if not fin:
            return
        px = valuation.price(self.client, t)
        self.count_error(f"Kurs {t}", None if px.get("kurs") else "kein_kurs")
        k = fin["kennzahlen"]
        shares = (fin.get("aktien_ausstehend") or {}).get("wert")
        mult = valuation.multiples(k, px, shares)
        rev = {}
        if mult.get("unternehmenswert") and k.get("umsatz_ttm") and k.get("fcf_marge_ttm"):
            for margin in sorted({round(k["fcf_marge_ttm"], 3), 0.25, 0.35}):
                g = valuation.implied_growth(mult["unternehmenswert"], k["umsatz_ttm"], margin)
                rev[f"{margin:.3f}"] = g
        th = thesis.load(t)
        ev = thesis.evaluate(th, fin, px, mult) if th else None
        p = store.company_dir(t) / "valuation.json"
        old = store.read_json(p, {}) or {}
        out = {"stand_utc": now_utc(), "kurs": px, "multiplikatoren": mult,
               "reverse_dcf": {"annahmen": {"diskontsatz": valuation.DISCOUNT, "wachstum_ewig": valuation.TERMINAL_G,
                                            "jahre": valuation.YEARS},
                               "impliziertes_umsatzwachstum_pa_je_fcf_marge": rev},
               "these": ev}
        if ev:
            self.thesis_changes(t, ev, (old.get("these") or {}))
        store.write_json(p, out)
        self.results[t] = {"fin": fin, "val": out, "these": th}

    def thesis_changes(self, t: str, ev: dict, old: dict) -> None:
        before = {(x["id"]): x.get("erfuellt") for x in old.get("einstieg", []) + old.get("widerlegung", [])}
        for kind, score in (("widerlegung", 1.0), ("einstieg", 0.9)):
            for c in ev[kind]:
                if c.get("erfuellt") and not before.get(c["id"]):
                    self.add(key=store.dedupe_key("these", f"{t}:{c['id']}:{date.today().isoformat()}"),
                             typ="these_ausloeser", ticker=t,
                             titel=f"{t}: {'Widerlegungsbedingung' if kind == 'widerlegung' else 'Einstiegskriterium'} erfüllt – {c['text']}",
                             quelle={"name": "Thesen-Prüfung (Python-Regel)", "url": f"research/desk/theses/{t}.json"},
                             stufe="A", veroeffentlicht=now_utc(), wichtigkeit=score,
                             gruende=[f"Regel {c['pruefung']} erfüllt, Istwerte {c.get('istwerte')}"], inhalt=c)

    # ---------------------------------------------------------------- Verknüpfung, Warteschlange, Speichern
    def link(self) -> None:
        """Regelbasierte Verknüpfung: Ergebnis-8-K (Item 2.02) und Pressemitteilung am selben/nächsten Tag."""
        pool = self.items + self.new
        for f in self.new:
            if f["typ"] != "pressemitteilung" or not f.get("veroeffentlicht"):
                continue
            words = " ".join(store.norm_title(f["titel"]))
            if not any(w in words for w in ("result", "financial", "earnings", "quarter", "fiscal")):
                continue
            d = f["veroeffentlicht"][:10]
            for g in pool:
                if (g["typ"] == "einreichung" and "2.02" in g.get("inhalt", {}).get("items", "")
                        and set(g["tickers"]) & set(f["tickers"]) and g.get("veroeffentlicht")
                        and abs(store._days(g["veroeffentlicht"][:10], d)) <= 1):
                    f["bezug"].append({"id": g["id"], "art": "gleiches Ereignis (Regel: Ergebnis-8-K ±1 Tag)"})

    def queue(self) -> list[dict]:
        out = []
        for f in self.new:
            if f["analyse"]["status"] != "angefordert":
                continue
            t = f["tickers"][0]
            res = self.results.get(t, {})
            ctx_prev = [{"id": i["id"], "typ": i["typ"], "titel": i["titel"], "veroeffentlicht": i.get("veroeffentlicht")}
                        for i in (self.items + self.new) if t in i.get("tickers", []) and i["id"] != f["id"]][-12:]
            job = {"id": f["id"], "erstellt_utc": now_utc(), "status": "offen", "ticker": t, "erkenntnis": f,
                   "kontext": {"fruehere_erkenntnisse": ctx_prev,
                               "finanzen": f"research/desk/companies/{t}/financials.json",
                               "bewertung": f"research/desk/companies/{t}/valuation.json",
                               "profil": f"research/desk/companies/{t}/profile.json",
                               "these": f"research/desk/theses/{t}.json" if res.get("these") else None,
                               "evidenz": f.get("evidenz")},
                   "fragen": ["Was hat sich verändert (nur belegte Fakten mit Quelle)?",
                              "Welche wirtschaftlichen Konsequenzen sind plausibel (mit Unsicherheit)?",
                              "Welche Unternehmen sind betroffen (nur mit belegtem Bezug)?",
                              "Welche Gegenargumente bestehen?",
                              "Welche Annahmen könnten bereits eingepreist sein (Reverse-DCF, Multiplikatoren)?",
                              "Ändert sich die These? Welche Bedingung wäre betroffen?"]}
            store.write_json(store.QUEUE / f"{f['id']}.json", job)
            out.append(job)
        return out

    def save(self) -> None:
        for f in self.new:
            store.append_finding(f)


def press_importance(title: str) -> tuple[float, list[str]]:
    t = title.lower()
    rules = [(("financial results", "quarter", "fiscal", "earnings", "revenue"), 0.75, "Ergebnisbezug im Titel"),
             (("acquire", "acquisition", "merger", "to buy"), 0.75, "Übernahme/Fusion im Titel"),
             (("ceo", "cfo", "chief executive", "appoints", "resign", "steps down"), 0.65, "Managementwechsel im Titel"),
             (("partnership", "agreement", "collaborat", "invest"), 0.50, "Partnerschaft/Vertrag im Titel"),
             (("dividend", "buyback", "repurchase"), 0.55, "Kapitalrückführung im Titel"),
             (("launch", "introduc", "announc", "unveil"), 0.35, "Produkt-/Allgemeinmeldung")]
    for words, score, why in rules:
        if any(w in t for w in words):
            return score, [why]
    return 0.30, ["allgemeine Unternehmensmeldung"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickers")
    ap.add_argument("--ohne-nachrichten", action="store_true")
    a = ap.parse_args()
    run = Run(a.tickers.split(",") if a.tickers else None, news=not a.ohne_nachrichten)
    started = now_utc()
    for c in run.universe:
        run.sec_filings(c)
        fin = run.sec_financials(c)
        run.newsroom(c)
        if run.news:
            run.gdelt(c)
        run.valuate(c, fin)
    run.link()
    run.save()
    jobs = run.queue()
    chain_ok, msg = store.verify_findings()
    total, failed = len(run.log.entries), len(run.log.errors())
    sec_ok = any(e.get("ok") and str(e.get("quelle", "")).startswith("SEC") for e in run.log.entries)
    # Erfolg = Datenbank intakt UND Primärquelle erreichbar UND weniger als die Hälfte der Abrufe gescheitert.
    # Sonst Exit 1 → Fehler-Issue im Workflow; der Heartbeat sieht keinen frischen Erfolg.
    ok = chain_ok and sec_ok and failed < max(1, total) / 2
    st = run.status
    st.update({"letzter_lauf_utc": started, "letzter_erfolg_utc": now_utc() if ok else st.get("letzter_erfolg_utc"),
               "letzter_lauf_ok": ok,
               "neue_erkenntnisse": len(run.new), "dubletten_verworfen": len(run.skipped),
               "analyseauftraege": len(jobs), "erkenntnisse_gesamt": len(store.findings()), "kette": msg,
               "abrufe": len(run.log.entries), "abruffehler": len(run.log.errors())})
    store.write_json(store.STATE, st)
    alerts = [f for f in run.new if f["wichtigkeit"]["wert"] >= ALERT_THRESHOLD and not f["erstlauf"]]
    write_report(run, jobs, alerts)
    flag = store.R / "alert.txt"
    if alerts:
        flag.write_text("; ".join(f"{f['tickers'][0]}: {f['titel'][:80]}" for f in alerts[:4])[:400])
    elif flag.exists():
        flag.unlink()
    print(f"Neu: {len(run.new)} · Dubletten: {len(run.skipped)} · Analyseaufträge: {len(jobs)} · "
          f"Abrufe: {len(run.log.entries)} (Fehler {len(run.log.errors())}) · {msg}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
