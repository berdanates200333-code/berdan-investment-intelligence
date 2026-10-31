"""Research-Monitor: Unternehmensdaten, SEC-Einreichungen und Nachrichten erfassen, Ereignisse erkennen.

Läuft in GitHub Actions (Internetzugang). Vollständig regelbasiert (Python) – KEINE KI.
Ereignisse hoher Wichtigkeit werden in research/queue/ für eine KI-Analyse (Claude) vorgemerkt.

Ausgaben:
  research/db/events.jsonl          append-only Ereignisspeicher (Hash-Kette)
  research/db/companies/<T>.json    aktuelles Unternehmensprofil (Kennzahlen, Segmente, Belege, Bewertung)
  research/db/companies/<T>.md      lesbares Profil
  research/sources/<T>/<acc>.txt    Text offizieller Pressemitteilungen (8-K Exhibit 99)
  research/queue/<id>.json          Analyseaufträge für Claude
  reports/research/latest.md        Kurzbericht
  reports/research/alert.txt        nur bei Benachrichtigungsbedarf (nicht versioniert)
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bii.research import evidence, feeds, fundamentals, news, sec, segments, valuation  # noqa: E402
from bii.research.events import Store, classify_filing, event_id, news_importance  # noqa: E402

DB = ROOT / "research" / "db"
STATE = DB / "state.json"
OPS = DB / "ops.json"
SEED_DAYS = 14          # Beim ersten Lauf: ältere Einreichungen nur als Bestand erfassen
QUEUE_MAX_AGE_DAYS = 7  # Nur frische Ereignisse werden zur KI-Analyse vorgemerkt


def load_json(p: Path, default):
    return json.loads(p.read_text()) if p.exists() else default


def save_json(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str))


def yahoo_quote(sym: str) -> dict | None:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=1mo&interval=1d"
    res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20).json()["chart"]["result"][0]
    closes = [c for c in res["indicators"]["quote"][0]["close"] if c is not None]
    ts = [t for t, c in zip(res["timestamp"], res["indicators"]["quote"][0]["close"]) if c is not None]
    if len(closes) < 2:
        return None
    return {"kurs": closes[-1], "vortag": closes[-2], "datum": datetime.fromtimestamp(ts[-1], timezone.utc).date().isoformat(),
            "waehrung": res["meta"].get("currency"), "quelle": "Yahoo Finance (inoffiziell, verzögert, ohne Zweitquelle)"}


class Run:
    def __init__(self, now: datetime):
        self.now = now
        self.iso = now.isoformat(timespec="seconds")
        self.store = Store()
        self.state = load_json(STATE, {"unternehmen": {}})
        self.ops = load_json(OPS, {"fehler": {}})
        self.errors: dict[str, str] = {}
        self.new: list[dict] = []
        self.queued: list[str] = []

    def err(self, key: str, e: Exception):
        self.errors[key] = f"{type(e).__name__}: {e}"[:300]
        print(f"FEHLER {key}: {self.errors[key]}", file=sys.stderr)

    def add(self, ev: dict, ticker_state: dict, seed: bool) -> dict | None:
        ev.setdefault("erfasst_utc", self.iso)
        if seed:
            ev["analyse_status"] = "bestand"
        e = self.store.add(ev)
        if e:
            self.new.append(e)
        return e

    # ------------------------------------------------------------------ SEC
    def sec_filings(self, c: dict, ts: dict, seed: bool):
        sub = sec.submissions(c["cik"])
        filings = sec.recent_filings(sub)[:60]
        cutoff = (self.now - timedelta(days=SEED_DAYS)).date().isoformat()
        for f in filings:
            eid = event_id("sec", c["ticker"], f["accessionNumber"])
            if eid in self.store.ids:
                continue
            label, imp, why = classify_filing(f["form"], f["items"])
            old = f["filingDate"] < cutoff
            ev = {"id": eid, "art": "sec", "ticker": c["ticker"], "titel": f"{f['form']}: {label}",
                  "formular": f["form"], "items": f["items"], "veroeffentlicht": f["acceptanceDateTime"] or f["filingDate"],
                  "berichtszeitraum": f.get("reportDate"), "quelle": {"url": sec.filing_url(c["cik"], f), "herausgeber": "SEC EDGAR",
                  "accession": f["accessionNumber"]}, "zuverlaessigkeit": "offiziell (Pflichtveröffentlichung, Primärquelle)",
                  "wichtigkeit": imp, "regel": why}
            if imp == "hoch" and f["form"].startswith("8-K") and not (seed and old):
                try:
                    pr = sec.press_release_url(c["cik"], f["accessionNumber"], f["primaryDocument"])
                    if pr:
                        txt = sec.fetch_text(pr, limit=60_000)
                        p = ROOT / "research" / "sources" / c["ticker"] / f"{f['accessionNumber']}.txt"
                        p.parent.mkdir(parents=True, exist_ok=True)
                        p.write_text(f"QUELLE: {pr}\nABGERUFEN: {self.iso}\n\n{txt}\n")
                        ev["quelltext"] = str(p.relative_to(ROOT))
                        ev["quelle"]["pressemitteilung"] = pr
                except Exception as e:  # noqa: BLE001
                    self.err(f"pressemitteilung:{c['ticker']}:{f['accessionNumber']}", e)
            self.add(ev, ts, seed and old)
        return filings

    # ------------------------------------------------------------------ Profil
    def company_profile(self, c: dict, ts: dict, filings: list[dict], seed: bool) -> dict:
        path = DB / "companies" / f"{c['ticker']}.json"
        old = load_json(path, None)
        prof = {"ticker": c["ticker"], "name": c["name"], "cik": c["cik"], "stand_utc": self.iso,
                "geschaeftsmodell": {"text": c.get("geschaeftsmodell"), "quelle": c.get("geschaeftsmodell_quelle")}}
        cf = sec.companyfacts(c["cik"])
        prof["finanzen"] = fundamentals.profile(cf)
        prof["finanzen"]["quelle"] = f"SEC XBRL companyfacts CIK{sec.cik10(c['cik'])}"
        # Segmente aus jüngstem 10-K oder 10-Q
        periodic = [f for f in filings if f["form"] in ("10-K", "10-Q")]
        if periodic:
            latest = periodic[0]
            if ts.get("segmente_accession") != latest["accessionNumber"] or not (old or {}).get("segmente"):
                try:
                    url = sec.xbrl_instance_url(c["cik"], latest["accessionNumber"])
                    seg = segments.parse(sec.get_raw(url)) if url else {}
                    prof["segmente"] = {**seg, "quelle": url, "formular": latest["form"], "accession": latest["accessionNumber"]}
                    ts["segmente_accession"] = latest["accessionNumber"]
                except Exception as e:  # noqa: BLE001
                    self.err(f"segmente:{c['ticker']}", e)
                    prof["segmente"] = (old or {}).get("segmente")
            else:
                prof["segmente"] = old.get("segmente")
        # Belegprüfung im jüngsten 10-K
        tenk = [f for f in filings if f["form"] == "10-K"]
        if tenk:
            k = tenk[0]
            if ts.get("belege_accession") != k["accessionNumber"] or not (old or {}).get("belege"):
                try:
                    url = sec.filing_url(c["cik"], k)
                    text = sec.fetch_text(url)
                    prof["belege"] = {"quelle": url, "accession": k["accessionNumber"], "geprueft_utc": self.iso,
                                      "item1_auszug": evidence.item1_excerpt(text),
                                      "management": evidence.check(text, c.get("management", [])),
                                      "beziehungen": evidence.check(text, c.get("beziehungen", []))}
                    ts["belege_accession"] = k["accessionNumber"]
                except Exception as e:  # noqa: BLE001
                    self.err(f"belege:{c['ticker']}", e)
                    prof["belege"] = (old or {}).get("belege")
            else:
                prof["belege"] = old.get("belege")
        # Kennzahlen-Veränderung als Ereignis
        changes = fundamentals.compare((old or {}).get("finanzen"), prof["finanzen"])
        new_ttm = prof["finanzen"]["ttm"].get("umsatz", {}).get("bis")
        if changes and new_ttm:
            src = prof["finanzen"]["ttm"]["umsatz"]["quellen"][-1]
            self.add({"id": event_id("kennzahlen", c["ticker"], new_ttm), "art": "kennzahlen", "ticker": c["ticker"],
                      "titel": f"Neue Quartalszahlen in XBRL-Daten (Quartal bis {new_ttm})",
                      "veroeffentlicht": src.get("eingereicht"), "quelle": {"url": prof["finanzen"]["quelle"],
                      "herausgeber": "SEC XBRL", "accession": src.get("accession")},
                      "zuverlaessigkeit": "offiziell (XBRL aus Pflichtveröffentlichung)", "wichtigkeit": "hoch",
                      "regel": "Regel: neues Quartal in den Finanzdaten", "details": {"veraenderungen": changes}}, ts, seed)
        return prof

    # ------------------------------------------------------------------ Kurs + Bewertung
    def price_and_valuation(self, c: dict, ts: dict, prof: dict, seed: bool):
        try:
            q = yahoo_quote(c["yahoo"])
        except Exception as e:  # noqa: BLE001
            self.err(f"kurs:{c['ticker']}", e)
            q = None
        prof["kurs"] = q
        if q and q["vortag"]:
            move = q["kurs"] / q["vortag"] - 1
            if abs(move) >= 0.08:
                self.add({"id": event_id("kurs", c["ticker"], q["datum"]), "art": "kurs", "ticker": c["ticker"],
                          "titel": f"Kursbewegung {move*100:+.1f} % am {q['datum']}", "veroeffentlicht": q["datum"],
                          "quelle": {"url": f"https://finance.yahoo.com/quote/{c['yahoo']}", "herausgeber": "Yahoo Finance"},
                          "zuverlaessigkeit": "Marktdaten, inoffiziell, ohne Zweitquelle", "wichtigkeit": "mittel",
                          "regel": "Regel: Tagesbewegung ≥ 8 %"}, ts, seed)
        thesis = load_json(ROOT / "research" / "theses" / f"{c['ticker']}.json", None)
        f = prof["finanzen"]
        k, t, b = f["kennzahlen"], f["ttm"], f["bilanz"]
        if not thesis or "bewertung" not in thesis or "umsatz" not in t or "aktien_ausstehend" not in b:
            return
        base = {"revenue0": t["umsatz"]["wert"], "fcf_margin_ttm": k.get("fcf_marge"),
                "net_cash": k.get("nettoliquiditaet", 0.0), "shares": b["aktien_ausstehend"]["wert"],
                "umsatz_ttm_bis": t["umsatz"]["bis"], "aktien_stichtag": b["aktien_ausstehend"]["stichtag"]}
        try:
            val = valuation.scenarios(base, thesis["bewertung"], q["kurs"] if q else None)
            ec = valuation.entry_check(val, q["kurs"] if q else None, thesis.get("einstieg", {}))
            val["einstieg"] = ec
            prof["bewertung"] = val
            was = ts.get("einstieg_erfuellt", False)
            if ec["erfuellt"] and not was:
                self.add({"id": event_id("einstieg", c["ticker"], q["datum"]), "art": "einstieg", "ticker": c["ticker"],
                          "titel": f"Einstiegskriterium der These erfüllt (Kurs {ec['kurs']:.2f} ≤ {ec['schwelle']:.2f})",
                          "veroeffentlicht": q["datum"], "quelle": {"url": f"research/theses/{c['ticker']}.json", "herausgeber": "Regelwerk"},
                          "zuverlaessigkeit": "Berechnung aus Annahmen + inoffiziellem Kurs", "wichtigkeit": "hoch",
                          "regel": ec["regel"]}, ts, seed)
            ts["einstieg_erfuellt"] = ec["erfuellt"]
        except Exception as e:  # noqa: BLE001
            self.err(f"bewertung:{c['ticker']}", e)

    # ------------------------------------------------------------------ Nachrichten
    def news(self, c: dict, ts: dict, seed: bool):
        """Nachrichten-Metadaten aus Google News RSS und Yahoo Finance RSS (GDELT drosselt GitHub-Server)."""
        arts, failed = [], 0
        for name, fn in (("google", lambda: feeds.google_news(c["google_news"])), ("yahoo", lambda: feeds.yahoo_news(c["yahoo"]))):
            try:
                arts += fn()
            except Exception as e:  # noqa: BLE001
                failed += 1
                self.err(f"news_{name}:{c['ticker']}", e)
        if failed == 2:
            raise RuntimeError("alle Nachrichtenquellen ausgefallen")
        added = dup = 0
        cutoff = (self.now - timedelta(days=3)).isoformat()
        for a in arts:
            if not a["url"] or not a["titel"] or (a.get("veroeffentlicht") and a["veroeffentlicht"] < cutoff):
                continue
            eid = event_id("news", c["ticker"], a["url"])
            if eid in self.store.ids:
                continue
            if self.store.is_duplicate_news(c["ticker"], a["titel"], self.now):
                dup += 1
                continue
            tier = news.domain_tier(a.get("domain") or "")
            imp, why = news_importance(a["titel"], tier)
            near = [e["id"] for e in self.store.events(c["ticker"], since=(self.now - timedelta(days=3)).isoformat())
                    if e["art"] in ("sec", "ir") and e["wichtigkeit"] == "hoch"]
            ev = {"id": eid, "art": "news", "ticker": c["ticker"], "titel": a["titel"], "veroeffentlicht": a.get("veroeffentlicht"),
                  "quelle": {"url": a["url"], "herausgeber": a.get("quelle_name") or a.get("domain"), "vermittler": a["vermittler"]},
                  "zuverlaessigkeit": f"Sekundärquelle, Stufe {tier}", "wichtigkeit": imp, "regel": why}
            if near:
                ev["zeitliche_naehe_zu"] = {"ereignisse": near, "hinweis": "nur zeitliche Nähe (≤3 Tage), kein inhaltlicher Nachweis"}
            if self.add(ev, ts, seed):
                added += 1
        hist = ts.setdefault("news_volumen", {})
        day = self.now.date().isoformat()
        hist[day] = hist.get(day, 0) + added
        for k in sorted(hist)[:-30]:
            hist.pop(k)
        prev = [v for k, v in sorted(hist.items()) if k < day][-14:]
        if len(prev) >= 7:
            med = sorted(prev)[len(prev) // 2]
            if hist[day] >= 15 and hist[day] > 3 * max(med, 1):
                self.add({"id": event_id("volumen", c["ticker"], day), "art": "volumen", "ticker": c["ticker"],
                          "titel": f"Ungewöhnlich viele Nachrichten: {hist[day]} heute vs. Median {med}",
                          "veroeffentlicht": day, "quelle": {"url": "Google News RSS / Yahoo Finance RSS", "herausgeber": "Aggregatoren"},
                          "zuverlaessigkeit": "Zählung von Sekundärquellen", "wichtigkeit": "mittel",
                          "regel": "Regel: Tagesanzahl > 3× Median der letzten 14 Tage und ≥ 15"}, ts, seed)
        ts["news_letzter_lauf"] = self.iso
        return {"neu": added, "dubletten": dup, "abgerufen": len(arts)}

    # ------------------------------------------------------------------ Offizielle Newsroom-/IR-Feeds
    def ir(self, c: dict, ts: dict, seed: bool) -> int:
        n = 0
        cutoff = (self.now - timedelta(days=SEED_DAYS)).isoformat()
        for url in c.get("ir_feeds", []):
            for it in feeds.fetch(url):
                if not it["url"] or not it["titel"]:
                    continue
                eid = event_id("ir", c["ticker"], hashlib.sha1(it["url"].encode()).hexdigest()[:16])
                if eid in self.store.ids:
                    continue
                imp, why = feeds.ir_importance(it["titel"])
                old = (it.get("veroeffentlicht") or self.iso) < cutoff
                ev = {"id": eid, "art": "ir", "ticker": c["ticker"], "titel": it["titel"], "veroeffentlicht": it.get("veroeffentlicht"),
                      "quelle": {"url": it["url"], "herausgeber": f"{c['name']} (offizieller Newsroom)", "feed": url},
                      "zuverlaessigkeit": "offiziell (Unternehmensmitteilung, Primärquelle)", "wichtigkeit": imp, "regel": why}
                if imp in ("hoch", "mittel") and not old:
                    try:
                        r = requests.get(it["url"], headers=feeds.UA, timeout=30)
                        r.raise_for_status()
                        txt = sec.html_to_text(r.text)[:60_000]
                        p = ROOT / "research" / "sources" / c["ticker"] / f"ir_{eid.split(':')[-1]}.txt"
                        p.parent.mkdir(parents=True, exist_ok=True)
                        p.write_text(f"QUELLE: {it['url']}\nABGERUFEN: {self.iso}\n\n{txt}\n")
                        ev["quelltext"] = str(p.relative_to(ROOT))
                    except Exception as e:  # noqa: BLE001
                        self.err(f"ir_text:{c['ticker']}", e)
                if self.add(ev, ts, seed and old):
                    n += 1
        return n

    # ------------------------------------------------------------------ Manuell angeforderte Analysen
    def request(self, ids: list[str]):
        """Ereignisse unabhängig von ihrer Wichtigkeit zur KI-Analyse vormerken (Quelltext wird geladen)."""
        byid = {e["id"]: e for e in self.store.events()}
        for eid in ids:
            e = byid.get(eid)
            if not e:
                self.errors[f"anforderung:{eid}|unbekannt"] = "Ereignis-ID nicht im Speicher"
                continue
            text_path = e.get("quelltext")
            if not text_path and e["quelle"].get("url", "").startswith("http"):
                try:
                    r = requests.get(e["quelle"]["url"], headers=feeds.UA, timeout=30)
                    r.raise_for_status()
                    p = ROOT / "research" / "sources" / e["ticker"] / f"angefordert_{hashlib.sha1(eid.encode()).hexdigest()[:12]}.txt"
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_text(f"QUELLE: {e['quelle']['url']}\nABGERUFEN: {self.iso}\n\n{sec.html_to_text(r.text)[:60_000]}\n")
                    text_path = str(p.relative_to(ROOT))
                except Exception as ex:  # noqa: BLE001
                    self.err(f"anforderung_text:{eid}", ex)
            self._enqueue(e, text_path, "manuell angefordert")

    def _enqueue(self, e: dict, text_path: str | None, reason: str):
        qid = re.sub(r"[^A-Za-z0-9_-]", "_", e["id"])
        p = ROOT / "research" / "queue" / f"{qid}.json"
        if p.exists():
            return
        save_json(p, {"ereignis_id": e["id"], "ticker": e["ticker"], "titel": e["titel"], "erstellt_utc": self.iso,
                      "status": "offen", "grund": reason, "kontext": {"ereignis": e, "profil": f"research/db/companies/{e['ticker']}.json",
                      "these": f"research/theses/{e['ticker']}.json", "quelltext": text_path},
                      "anleitung": ".claude/commands/research-analyse.md"})
        self.store.set_status(e["id"], "zur_analyse_vorgemerkt", reason)
        self.queued.append(e["id"])

    # ------------------------------------------------------------------ Analyse-Warteschlange
    def queue(self):
        cutoff = (self.now - timedelta(days=QUEUE_MAX_AGE_DAYS)).isoformat()
        for e in self.new:
            if e["wichtigkeit"] != "hoch" or e.get("analyse_status") == "bestand":
                continue
            if (e.get("veroeffentlicht") or e["erfasst_utc"]) < cutoff[:10]:
                continue
            self._enqueue(e, e.get("quelltext"), "Regel: Wichtigkeit hoch")


def main(now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    run = Run(now)
    cfg = yaml.safe_load((ROOT / "research" / "companies.yaml").read_text())["unternehmen"]
    profiles, newsstats, ok_tickers = {}, {}, []
    sec_ok = bool(os.environ.get("SEC_USER_AGENT"))
    if not sec_ok:
        run.errors["sec:alle|kontakt_fehlt"] = ("SEC verlangt einen User-Agent mit echter Kontaktadresse: Repository-Variable "
                                                 "SEC_USER_AGENT setzen (z. B. 'Vorname Nachname name@domain.de').")
    for c in cfg:
        t = c["ticker"]
        ts = run.state["unternehmen"].setdefault(t, {})
        seed = not ts.get("initialisiert")
        old = load_json(DB / "companies" / f"{t}.json", None) or {}
        filings, prof, got = [], None, 0
        if sec_ok:
            sec_seed = not ts.get("sec_initialisiert")
            try:
                filings = run.sec_filings(c, ts, sec_seed)
                got += 1
            except Exception as e:  # noqa: BLE001
                run.err(f"sec:{t}", e)
            try:
                prof = run.company_profile(c, ts, filings, sec_seed)
                prof["sec_daten_status"] = "aktuell"
            except Exception as e:  # noqa: BLE001
                run.err(f"profil:{t}", e)
                traceback.print_exc()
            if filings:
                ts["sec_initialisiert"] = True
        if prof is None:   # ohne SEC: Grundprofil; frühere SEC-Daten bleiben erhalten und werden als nicht aktualisiert markiert
            prof = {**old, "ticker": t, "name": c["name"], "cik": c["cik"], "stand_utc": run.iso,
                    "geschaeftsmodell": {"text": c.get("geschaeftsmodell"), "quelle": c.get("geschaeftsmodell_quelle")},
                    "finanzen": old.get("finanzen") or {"ttm": {}, "kennzahlen": {}, "bilanz": {}, "quartale": {}},
                    "sec_daten_status": "nicht aktualisiert (SEC nicht erreichbar)" if old.get("finanzen") else "fehlt (SEC nicht erreichbar)"}
        try:
            run.price_and_valuation(c, ts, prof, seed)
        except Exception as e:  # noqa: BLE001
            run.err(f"bewertung:{t}", e)
        try:
            prof["ir_neu"] = run.ir(c, ts, seed)
            got += 1
        except Exception as e:  # noqa: BLE001
            run.err(f"ir:{t}", e)
        try:
            newsstats[t] = run.news(c, ts, seed)
            got += 1
        except Exception as e:  # noqa: BLE001
            run.err(f"news:{t}", e)
        save_json(DB / "companies" / f"{t}.json", prof)
        profiles[t] = prof
        if got:
            ts["initialisiert"] = True
            ok_tickers.append(t)
    run.queue()
    req = [x.strip() for x in os.environ.get("ANALYSE_ANFORDERN", "").split(",") if x.strip()]
    if req:
        run.request(req)
    # Fehlerzähler je Quelle/Unternehmen/Ursache (aufeinanderfolgende Läufe)
    for k in list(run.ops["fehler"]):
        if k not in run.errors:
            run.ops["fehler"].pop(k)
    for k, msg in run.errors.items():
        prev = run.ops["fehler"].get(k, {"folge": 0})
        run.ops["fehler"][k] = {"folge": prev["folge"] + 1, "letzte_meldung": msg}
    run.ops["letzter_lauf_utc"] = run.iso
    # "Erfolg" = für jedes Unternehmen lieferte mindestens eine Quelle Daten (nicht nur: Skript lief durch)
    if len(ok_tickers) == len(cfg):
        run.ops["letzter_erfolg_utc"] = run.iso
    run.ops["quellenstatus"] = {"sec": "aktiv" if sec_ok else "inaktiv (Kontaktangabe fehlt)",
                                "unternehmen_mit_daten": ok_tickers}
    save_json(STATE, run.state)
    save_json(OPS, run.ops)
    from bii.research import report
    report.write_all(run, cfg, profiles, newsstats)  # nutzt run.ops["quellenstatus"]
    return 0


if __name__ == "__main__":
    sys.exit(main())
