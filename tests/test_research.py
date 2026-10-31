"""Tests des Research-Prototyps. Synthetische Daten im Format der SEC-/GDELT-Antworten – nur Code-Prüfung."""
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bii.research import evidence, events, fundamentals, segments, valuation  # noqa: E402


def fact(start, end, val, form, filed, accn="0000000000-26-000001", fy=None):
    f = {"end": end, "val": val, "form": form, "filed": filed, "accn": accn}
    if start:
        f["start"] = start
    return f


def companyfacts():
    """GJ = Kalenderjahr. 10-Q liefern 3M-Umsätze; Cashflow nur kumuliert (YTD); 10-K Jahreswerte."""
    rev = [fact("2025-01-01", "2025-03-31", 100, "10-Q", "2025-04-30"), fact("2025-04-01", "2025-06-30", 110, "10-Q", "2025-07-30"),
           fact("2025-07-01", "2025-09-30", 120, "10-Q", "2025-10-30"), fact("2025-01-01", "2025-12-31", 470, "10-K", "2026-02-20"),
           fact("2026-01-01", "2026-03-31", 150, "10-Q", "2026-04-30"),
           # Restatement: späterer Bericht korrigiert Q1/2025 auf 101
           fact("2025-01-01", "2025-03-31", 101, "10-Q", "2026-04-30")]
    cfo = [fact("2025-01-01", "2025-03-31", 30, "10-Q", "2025-04-30"), fact("2025-01-01", "2025-06-30", 65, "10-Q", "2025-07-30"),
           fact("2025-01-01", "2025-09-30", 100, "10-Q", "2025-10-30"), fact("2025-01-01", "2025-12-31", 140, "10-K", "2026-02-20"),
           fact("2026-01-01", "2026-03-31", 50, "10-Q", "2026-04-30")]
    capex = [fact(s, e, v / 5, fo, fi) for s, e, v, fo, fi in [(f["start"], f["end"], f["val"], f["form"], f["filed"]) for f in cfo]]
    return {"facts": {
        "us-gaap": {
            "RevenueFromContractWithCustomerExcludingAssessedTax": {"units": {"USD": rev}},
            "NetCashProvidedByUsedInOperatingActivities": {"units": {"USD": cfo}},
            "PaymentsToAcquirePropertyPlantAndEquipment": {"units": {"USD": capex}},
            "OperatingIncomeLoss": {"units": {"USD": [fact(f["start"], f["end"], f["val"] * 0.4, f["form"], f["filed"]) for f in rev[:5]]}},
            "CashAndCashEquivalentsAtCarryingValue": {"units": {"USD": [fact(None, "2026-03-31", 200, "10-Q", "2026-04-30")]}},
            "LongTermDebtNoncurrent": {"units": {"USD": [fact(None, "2026-03-31", 50, "10-Q", "2026-04-30")]}},
        },
        "dei": {"EntityCommonStockSharesOutstanding": {"units": {"shares": [fact(None, "2026-04-20", 10, "10-Q", "2026-04-30")]}}},
    }}


def test_quarterly_derivation_and_ttm():
    cf = companyfacts()
    q = fundamentals.quarterly(cf, fundamentals.FLOW["umsatz"])
    vals = {x["ende"]: x["wert"] for x in q}
    assert vals["2025-03-31"] == 101                     # Restatement (später eingereicht) gewinnt
    assert vals["2025-12-31"] == 470 - 120 - 110 - 101   # Q4 = GJ minus Q1–Q3 (Q1 korrigiert)
    t = fundamentals.ttm(q)
    assert t["bis"] == "2026-03-31" and t["wert"] == 110 + 120 + vals["2025-12-31"] + 150
    cfo = {x["ende"]: x for x in fundamentals.quarterly(cf, fundamentals.FLOW["operativer_cashflow"])}
    assert cfo["2025-06-30"]["wert"] == 35 and "abgeleitet" in cfo["2025-06-30"]["quelle"]
    assert cfo["2025-12-31"]["wert"] == 40                 # 140 − 100


def test_profile_metrics_have_sources():
    p = fundamentals.profile(companyfacts())
    k = p["kennzahlen"]
    assert k["nettoliquiditaet"] == 150
    assert abs(k["fcf_marge"] - 0.8 * (35 + 35 + 40 + 50) / p["ttm"]["umsatz"]["wert"]) < 1e-9
    assert p["ttm"]["umsatz"]["quellen"][-1]["accession"]
    assert p["bilanz"]["aktien_ausstehend"]["wert"] == 10


def test_compare_detects_new_quarter():
    cf = companyfacts()
    new = fundamentals.profile(cf)
    cf2 = json.loads(json.dumps(cf))
    rev = cf2["facts"]["us-gaap"]["RevenueFromContractWithCustomerExcludingAssessedTax"]["units"]["USD"]
    cf2["facts"]["us-gaap"]["RevenueFromContractWithCustomerExcludingAssessedTax"]["units"]["USD"] = [f for f in rev if f["end"] != "2026-03-31"]
    old = fundamentals.profile(cf2)
    ch = fundamentals.compare(old, new)
    assert any(c["kennzahl"] == "umsatz_ttm" for c in ch)
    assert fundamentals.compare(new, new) == []


XBRL = b"""<?xml version="1.0"?>
<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:xbrldi="http://xbrl.org/2006/xbrldi"
 xmlns:us-gaap="http://fasb.org/us-gaap/2025" xmlns:x="http://x.com/2025">
 <xbrli:context id="FY"><xbrli:entity><xbrli:identifier scheme="s">1</xbrli:identifier></xbrli:entity>
  <xbrli:period><xbrli:startDate>2025-01-27</xbrli:startDate><xbrli:endDate>2026-01-25</xbrli:endDate></xbrli:period></xbrli:context>
 <xbrli:context id="FY_DC"><xbrli:entity><xbrli:identifier scheme="s">1</xbrli:identifier><xbrli:segment>
  <xbrldi:explicitMember dimension="us-gaap:StatementBusinessSegmentsAxis">x:ComputeAndNetworkingMember</xbrldi:explicitMember></xbrli:segment></xbrli:entity>
  <xbrli:period><xbrli:startDate>2025-01-27</xbrli:startDate><xbrli:endDate>2026-01-25</xbrli:endDate></xbrli:period></xbrli:context>
 <xbrli:context id="FY_G"><xbrli:entity><xbrli:identifier scheme="s">1</xbrli:identifier><xbrli:segment>
  <xbrldi:explicitMember dimension="us-gaap:StatementBusinessSegmentsAxis">x:GraphicsMember</xbrldi:explicitMember></xbrli:segment></xbrli:entity>
  <xbrli:period><xbrli:startDate>2025-01-27</xbrli:startDate><xbrli:endDate>2026-01-25</xbrli:endDate></xbrli:period></xbrli:context>
 <xbrli:context id="PY"><xbrli:entity><xbrli:identifier scheme="s">1</xbrli:identifier></xbrli:entity>
  <xbrli:period><xbrli:startDate>2024-01-29</xbrli:startDate><xbrli:endDate>2025-01-26</xbrli:endDate></xbrli:period></xbrli:context>
 <us-gaap:Revenues contextRef="FY" unitRef="usd" decimals="-6">200000000000</us-gaap:Revenues>
 <us-gaap:Revenues contextRef="PY" unitRef="usd" decimals="-6">130000000000</us-gaap:Revenues>
 <us-gaap:Revenues contextRef="FY_DC" unitRef="usd" decimals="-6">180000000000</us-gaap:Revenues>
 <us-gaap:Revenues contextRef="FY_G" unitRef="usd" decimals="-6">20000000000</us-gaap:Revenues>
 <us-gaap:OperatingIncomeLoss contextRef="FY_DC" unitRef="usd" decimals="-6">120000000000</us-gaap:OperatingIncomeLoss>
</xbrli:xbrl>"""


def test_segments_parse():
    s = segments.parse(XBRL)
    seg = s["achsen"]["Geschäftssegmente"]
    assert s["periode"]["bis"] == "2026-01-25" and s["gesamtumsatz"] == 2e11
    assert seg["Compute And Networking"]["anteil"] == 0.9 and seg["Compute And Networking"]["operatives_ergebnis"] == 1.2e11
    assert abs(s["abdeckung"]["Geschäftssegmente"] - 1.0) < 1e-9


def test_classify_rules():
    assert events.classify_filing("8-K", "2.02,9.01")[1] == "hoch"
    assert events.classify_filing("8-K", "5.02")[1] == "mittel"
    assert events.classify_filing("8-K", "9.01")[1] == "niedrig"
    assert events.classify_filing("10-Q", "")[1] == "hoch"
    assert events.classify_filing("4", "")[1] == "niedrig"
    assert events.news_importance("Nvidia faces new export ban on chips", "A (etabliertes Wirtschaftsmedium)")[0] == "mittel"
    assert events.news_importance("Nvidia faces new export ban on chips", "C (unbekannt/ungeprüft)")[0] == "niedrig"


def test_store_dedupe_and_chain(tmp_path):
    p = tmp_path / "ev.jsonl"
    s = events.Store(p)
    now = datetime(2026, 11, 1, tzinfo=timezone.utc)
    ev = {"id": events.event_id("news", "NVDA", "https://www.reuters.com/a/b/?utm=x"), "art": "news", "ticker": "NVDA",
          "titel": "Nvidia unveils new chip - Reuters", "wichtigkeit": "niedrig"}
    assert s.add(ev, now) and s.add(ev, now) is None
    # gleiche URL mit anderem Tracking-Parameter -> gleiche ID
    assert events.event_id("news", "NVDA", "http://reuters.com/a/b") == ev["id"]
    assert s.is_duplicate_news("NVDA", "Nvidia unveils new chip", now)
    assert not s.is_duplicate_news("AMD", "Nvidia unveils new chip", now)
    s.set_status(ev["id"], "analysiert", now=now)
    s2 = events.Store(p)
    assert s2.status_of(ev["id"]) == "analysiert"
    from bii import journal
    assert journal.verify(p)[0]


def test_valuation_consistency():
    r = valuation.dcf(100.0, 0.10, 0.05, 0.25, 0.09, 0.03, 20.0, 10.0)
    assert r["wert_je_aktie"] > 0 and 0 < r["anteil_endwert"] < 1
    mc = valuation.dcf(100.0, 0.12, 0.12, 0.25, 0.09, 0.03, 20.0, 1.0)["eigenkapitalwert"]
    g = valuation.implied_growth(mc, 100.0, 0.25, 0.09, 0.03, 20.0)
    assert abs(g - 0.12) < 1e-6
    with pytest.raises(ValueError):
        valuation.dcf(100, 0.1, 0.1, 0.2, 0.03, 0.03, 0, 1)


def test_evidence_check():
    text = "We utilize foundries, such as Taiwan Semiconductor Manufacturing Company Limited, or TSMC, and Samsung."
    out = evidence.check(text, [{"partner": "TSMC", "pruefwort": "Taiwan Semiconductor"}, {"partner": "X", "pruefwort": "Globalfoo"}])
    assert out[0]["beleg"].startswith("im 10-K gefunden") and "foundries" in out[0]["ausschnitt"]
    assert "unbestätigt" in out[1]["beleg"]


# ------------------------------------------------------------------ Offline-Gesamtlauf des Monitors
@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    import scripts.research_monitor as rm
    from bii.research import report
    (tmp_path / "research" / "db").mkdir(parents=True)
    shutil.copy(ROOT / "research" / "companies.yaml", tmp_path / "research" / "companies.yaml")
    monkeypatch.setattr(rm, "ROOT", tmp_path)
    monkeypatch.setattr(rm, "DB", tmp_path / "research" / "db")
    monkeypatch.setattr(rm, "STATE", tmp_path / "research" / "db" / "state.json")
    monkeypatch.setattr(rm, "OPS", tmp_path / "research" / "db" / "ops.json")
    monkeypatch.setattr(events.Store.__init__, "__defaults__", (tmp_path / "research" / "db" / "events.jsonl",))
    monkeypatch.setattr(report, "ROOT", tmp_path)
    monkeypatch.setattr(report, "REP", tmp_path / "reports" / "research")

    def subs(cik):
        acc = [f"000{cik}-26-00000{i}" for i in range(4)]
        return {"filings": {"recent": {
            "accessionNumber": acc, "filingDate": ["2026-10-29", "2026-10-29", "2026-08-01", "2026-10-30"],
            "acceptanceDateTime": ["2026-10-29T20:05:00.000Z", "2026-10-29T20:10:00.000Z", "2026-08-01T20:00:00.000Z", ""],
            "form": ["8-K", "10-Q", "10-K", "4"], "items": ["2.02,9.01", "", "", ""],
            "primaryDocument": ["a.htm", "q.htm", "k.htm", "f4.xml"], "primaryDocDescription": [""] * 4, "reportDate": [""] * 4}}}
    monkeypatch.setattr(rm.sec, "submissions", subs)
    monkeypatch.setattr(rm.sec, "companyfacts", lambda cik: companyfacts())
    monkeypatch.setattr(rm.sec, "press_release_url", lambda *a: "https://sec.example/ex99.htm")
    monkeypatch.setattr(rm.sec, "fetch_text", lambda url, limit=None: "Item 1. Business ... TOC\n" + "Item 1. Business " + "We design accelerated computing. Taiwan Semiconductor Jensen " * 30)
    monkeypatch.setattr(rm.sec, "xbrl_instance_url", lambda *a: "https://sec.example/x_htm.xml")
    monkeypatch.setattr(rm.sec, "get_raw", lambda url: XBRL)
    monkeypatch.setattr(rm, "yahoo_quote", lambda s: {"kurs": 50.0, "vortag": 49.0, "datum": "2026-10-30", "waehrung": "USD", "quelle": "test"})
    monkeypatch.setenv("SEC_USER_AGENT", "Test Kontakt test@example.org")
    monkeypatch.setattr(rm.feeds, "google_news", lambda q: [
        {"titel": "Chipmaker beats forecast, raises outlook", "url": "https://news.google.com/rss/articles/x1", "domain": "www.reuters.com",
         "quelle_name": "Reuters", "veroeffentlicht": "2026-10-30T10:00:00+00:00", "vermittler": "Google News RSS"}])
    monkeypatch.setattr(rm.feeds, "yahoo_news", lambda t: [
        {"titel": "Chipmaker beats forecast, raises outlook - Yahoo", "url": "https://finance.yahoo.com/y", "domain": "finance.yahoo.com",
         "quelle_name": None, "veroeffentlicht": "2026-10-30T11:00:00+00:00", "vermittler": "Yahoo Finance RSS"}])
    monkeypatch.setattr(rm.feeds, "fetch", lambda url: [
        {"titel": "Company Announces Financial Results for Third Quarter Fiscal 2027", "url": "https://ir.example/q3",
         "veroeffentlicht": "2026-10-29T20:05:00+00:00"},
        {"titel": "Company celebrates anniversary", "url": "https://ir.example/old", "veroeffentlicht": "2026-08-01T10:00:00+00:00"}])

    class R:
        text = "<html><body><p>Revenue was $57.0 billion.</p></body></html>"

        def raise_for_status(self):
            pass
    monkeypatch.setattr(rm.requests, "get", lambda *a, **k: R())
    monkeypatch.setattr(rm.time, "sleep", lambda s: None)
    return tmp_path, rm


def test_monitor_end_to_end(sandbox):
    tmp, rm = sandbox
    now = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)
    assert rm.main(now) == 0
    s = events.Store(tmp / "research" / "db" / "events.jsonl")
    ev = s.events("NVDA")
    kinds = {e["art"] for e in ev}
    assert {"sec", "news", "ir"} <= kinds
    ir = {e["titel"]: e for e in ev if e["art"] == "ir"}
    assert ir["Company Announces Financial Results for Third Quarter Fiscal 2027"]["wichtigkeit"] == "hoch"
    assert ir["Company celebrates anniversary"]["analyse_status"] == "bestand"
    assert sum(e["art"] == "news" for e in ev) == 1                       # Titel-Dublette verworfen
    tenk = [e for e in ev if e.get("formular") == "10-K"][0]
    assert tenk["analyse_status"] == "bestand"                             # älter als 14 Tage beim Erstlauf
    queue = sorted(p.name for p in (tmp / "research" / "queue").glob("*.json"))
    assert any("NVDA" in q for q in queue)                                 # frisches 8-K 2.02 vorgemerkt
    prof = json.loads((tmp / "research" / "db" / "companies" / "NVDA.json").read_text())
    assert prof["segmente"]["achsen"] and prof["belege"]["beziehungen"][0]["beleg"].startswith("im 10-K gefunden")
    assert (tmp / "research" / "sources" / "NVDA").exists()
    assert (tmp / "reports" / "research" / "alert.txt").exists()
    # Zweiter Lauf: nichts Neues -> keine Benachrichtigung, keine neuen Ereignisse
    n_before = len(s.entries)
    assert rm.main(datetime(2026, 10, 31, 18, 0, tzinfo=timezone.utc)) == 0
    assert not (tmp / "reports" / "research" / "alert.txt").exists()
    assert len(events.Store(tmp / "research" / "db" / "events.jsonl").entries) == n_before


def test_monitor_without_sec_contact(sandbox, monkeypatch):
    tmp, rm = sandbox
    monkeypatch.delenv("SEC_USER_AGENT")
    monkeypatch.setattr(rm.sec, "submissions", lambda cik: (_ for _ in ()).throw(AssertionError("SEC darf nicht aufgerufen werden")))
    assert rm.main(datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)) == 0
    ops = json.loads((tmp / "research" / "db" / "ops.json").read_text())
    assert "sec:alle|kontakt_fehlt" in ops["fehler"] and ops["quellenstatus"]["sec"].startswith("inaktiv")
    prof = json.loads((tmp / "research" / "db" / "companies" / "MSFT.json").read_text())
    assert prof["sec_daten_status"].startswith("fehlt")
    assert ops.get("letzter_erfolg_utc")   # Newsroom + Nachrichten lieferten Daten
