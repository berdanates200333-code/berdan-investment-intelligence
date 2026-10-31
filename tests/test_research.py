"""Tests des Research-Desks (offline, mit Testdaten im Format der echten SEC-Antworten)."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bii.research import feeds, financials, sec, store, thesis, valuation  # noqa: E402
from bii.research.http import FetchError  # noqa: E402


def fact(start, end, val, form, filed, accn, fp="Q"):
    d = {"end": end, "val": val, "form": form, "filed": filed, "accn": accn, "fp": fp}
    if start:
        d["start"] = start
    return d


def facts_fixture():
    # Geschäftsjahr 1.1.–31.12.; GuV als 3-Monats-Werte, Cashflow nur kumuliert (wie in echten 10-Q)
    rev = [
        fact("2024-01-01", "2024-03-31", 100, "10-Q", "2024-04-25", "a1"),
        fact("2024-04-01", "2024-06-30", 110, "10-Q", "2024-07-25", "a2"),
        fact("2024-07-01", "2024-09-30", 120, "10-Q", "2024-10-25", "a3"),
        fact("2024-01-01", "2024-12-31", 460, "10-K", "2025-02-10", "a4", "FY"),
        fact("2025-01-01", "2025-03-31", 150, "10-Q", "2025-04-25", "b1"),
        fact("2025-04-01", "2025-06-30", 170, "10-Q", "2025-07-25", "b2"),
        # spätere Korrektur des Q2-2025-Werts in einer neueren Einreichung
        fact("2025-04-01", "2025-06-30", 172, "10-Q", "2025-10-25", "b3"),
        fact("2025-07-01", "2025-09-30", 190, "10-Q", "2025-10-25", "b3"),
    ]
    ocf = [
        fact("2024-01-01", "2024-03-31", 30, "10-Q", "2024-04-25", "a1"),
        fact("2024-01-01", "2024-06-30", 65, "10-Q", "2024-07-25", "a2"),
        fact("2024-01-01", "2024-09-30", 100, "10-Q", "2024-10-25", "a3"),
        fact("2024-01-01", "2024-12-31", 140, "10-K", "2025-02-10", "a4", "FY"),
        fact("2025-01-01", "2025-03-31", 40, "10-Q", "2025-04-25", "b1"),
        fact("2025-01-01", "2025-06-30", 90, "10-Q", "2025-07-25", "b2"),
        fact("2025-01-01", "2025-09-30", 150, "10-Q", "2025-10-25", "b3"),
    ]
    capex = [fact(s, e, v / 10, f, fi, a) for s, e, v, f, fi, a in
             [(x["start"], x["end"], x["val"], x["form"], x["filed"], x["accn"]) for x in ocf]]
    gp = [fact(x["start"], x["end"], x["val"] * 0.6, x["form"], x["filed"], x["accn"]) for x in rev]
    cash = [fact(None, "2025-09-30", 500, "10-Q", "2025-10-25", "b3")]
    debt = [fact(None, "2025-09-30", 200, "10-Q", "2025-10-25", "b3")]
    shares = [{"end": "2025-10-20", "val": 10, "form": "10-Q", "filed": "2025-10-25", "accn": "b3"}]
    usd = lambda rows: {"units": {"USD": rows}}  # noqa: E731
    return {"facts": {"us-gaap": {"RevenueFromContractWithCustomerExcludingAssessedTax": usd(rev),
                                  "NetCashProvidedByUsedInOperatingActivities": usd(ocf),
                                  "PaymentsToAcquirePropertyPlantAndEquipment": usd(capex),
                                  "GrossProfit": usd(gp), "NetIncomeLoss": usd([fact(x["start"], x["end"], x["val"] * 0.3, x["form"], x["filed"], x["accn"]) for x in rev]),
                                  "CashAndCashEquivalentsAtCarryingValue": usd(cash), "LongTermDebtNoncurrent": usd(debt)},
                      "dei": {"EntityCommonStockSharesOutstanding": {"units": {"shares": shares}}}},
            "_meta": {"url": "https://data.sec.gov/api/xbrl/companyfacts/CIK0000000001.json", "abgerufen_utc": "2025-11-01T00:00:00+00:00"}}


def test_quarters_derived_from_cumulative_and_q4():
    c, q = financials.flow_series(facts_fixture(), financials.FLOW["operativer_cashflow"])
    vals = {x["ende"]: (x["wert"], x["abgeleitet"]) for x in q}
    assert vals["2024-06-30"] == (35, True)     # 65 − 30
    assert vals["2024-09-30"] == (35, True)     # 100 − 65
    assert vals["2024-12-31"] == (40, True)     # Gesamtjahr 140 − 9 Monate 100
    assert vals["2025-09-30"] == (60, True)
    c, r = financials.flow_series(facts_fixture(), financials.FLOW["umsatz"])
    rv = {x["ende"]: x["wert"] for x in r}
    assert rv["2024-12-31"] == 130               # Q4 = 460 − (100+110+120)
    assert rv["2025-06-30"] == 172               # jüngste Einreichung gilt


def test_metrics_ttm_growth_margins_and_restatement():
    fin = financials.build(facts_fixture())
    k = fin["kennzahlen"]
    assert k["letztes_quartal"] == "2025-09-30"
    assert k["umsatz_ttm"] == 130 + 150 + 172 + 190
    assert k["umsatzwachstum_yoy_q"] == pytest.approx(190 / 120 - 1)
    assert k["bruttomarge_q"] == pytest.approx(0.6)
    assert k["fcf_ttm"] == pytest.approx((40 + 40 + 50 + 60) * 0.9)
    assert k["nettoliquiditaet"] == 300
    assert any(r["ende"] == "2025-06-30" and r["alt"] == 170 and r["neu"] == 172 for r in fin["korrekturen"])


def test_8k_item_importance_and_forms():
    s, why = sec.filing_importance({"form": "8-K", "items": "2.02,9.01"})
    assert s == 0.9 and "2.02" in why[0]
    assert sec.filing_importance({"form": "8-K", "items": "4.02"})[0] == 1.0
    assert sec.filing_importance({"form": "4"})[0] < 0.3
    assert sec.filing_importance({"form": "10-K"})[0] >= 0.7


def test_recent_filings_columns_to_rows_and_urls():
    sub = {"cik": "1045810", "filings": {"recent": {"accessionNumber": ["0001045810-25-000001"], "form": ["8-K"],
                                                      "filingDate": ["2025-11-19"], "primaryDocument": ["x.htm"], "items": ["2.02"]}}}
    f = sec.recent_filings(sub)[0]
    assert f["filing_url"] == "https://www.sec.gov/Archives/edgar/data/1045810/000104581025000001/x.htm"
    assert sec.pick_press_release([{"name": "x.htm"}, {"name": "q3fy26pr-ex99_1.htm"}]) == "q3fy26pr-ex99_1.htm"


def test_html_to_text():
    t = sec.html_to_text("<html><head><style>x{}</style></head><body><p>Revenue&nbsp;was $1.0 billion.</p><table><tr><td>A</td><td>1</td></tr></table></body></html>")
    assert "Revenue was $1.0 billion." in t and "x{}" not in t


def test_feed_parsing_rss_and_atom():
    rss = """<rss><channel><item><title>NVIDIA Announces Financial Results</title><link>https://n.example/a</link>
             <pubDate>Wed, 19 Nov 2025 21:20:00 GMT</pubDate><description>&lt;p&gt;Record revenue&lt;/p&gt;</description></item></channel></rss>"""
    atom = """<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>T</title><link href="https://m.example/b"/>
              <published>2025-11-20T10:00:00Z</published><summary>S</summary></entry></feed>"""
    a = feeds.parse_feed(rss)[0]
    assert a["veroeffentlicht"] == "2025-11-19T21:20:00+00:00" and a["anriss"] == "Record revenue"
    assert feeds.parse_feed(atom)[0]["link"] == "https://m.example/b"


def test_dedupe_by_key_url_and_similar_title():
    idx = store.Index([{"id": "x1", "dedupe_key": "sec:1", "typ": "pressemitteilung", "tickers": ["NVDA"],
                        "titel": "NVIDIA Announces Financial Results for Third Quarter Fiscal 2026",
                        "veroeffentlicht": "2025-11-19T21:20:00+00:00", "quelle": {"url": "https://www.n.example/a?utm=1"}}])
    assert idx.duplicate_of("sec:1", None, None, ["NVDA"], None)
    assert idx.duplicate_of("url:new", "http://n.example/a/", None, ["NVDA"], None) == "gleiche URL"
    assert "nahezu gleicher Titel" in idx.duplicate_of("url:z", "https://other/z", "NVIDIA announces financial results for the third quarter fiscal 2026",
                                                        ["NVDA"], "2025-11-20")
    # gleicher Titel bei anderem Unternehmen ist KEINE Dublette (keine erfundenen Zusammenhänge)
    assert idx.duplicate_of("url:y", "https://other/y", "NVIDIA Announces Financial Results for Third Quarter Fiscal 2026",
                            ["AMD"], "2025-11-19") is None


def test_reverse_dcf_roundtrip():
    ev = valuation.dcf_value(100.0, 0.12, 0.3)
    g = valuation.implied_growth(ev, 100.0, 0.3)
    assert g == pytest.approx(0.12, abs=1e-6)
    assert valuation.implied_growth(1e12, 1.0, 0.3) is None   # außerhalb des Suchbereichs → keine Scheinpräzision


def test_thesis_checks(tmp_path, monkeypatch):
    fin = financials.build(facts_fixture())
    th = {"szenarien": [{"name": "neutral", "umsatz_cagr": 0.1, "fcf_marge": 0.25, "ev_fcf_multiple": 20, "jahre": 5}],
          "einstiegskriterien": [{"id": "E1", "text": "Kurs ≤ 80 % des Basiswerts", "pruefung": {"metrik": "kurs_zu_basiswert", "op": "<=", "wert": 0.8}}],
          "widerlegung": [{"id": "W1", "text": "Wachstum < 0 % zwei Quartale", "pruefung": {"metrik": "umsatzwachstum_yoy_letzte_n", "op": "<", "wert": 0, "n": 2}},
                          {"id": "W2", "text": "Management-Glaubwürdigkeit"}]}
    ev = thesis.evaluate(th, fin, {"kurs": 1.0}, {})
    assert ev["einstieg"][0]["erfuellt"] is True          # Kurs 1 USD weit unter Basiswert
    assert ev["widerlegung"][0]["erfuellt"] is False
    assert ev["widerlegung"][1]["status"] == "manuell"


class FakeClient:
    """Liefert Testdaten statt Netzabrufen; protokolliert wie der echte Client."""

    def __init__(self, routes, log):
        self.routes, self.log = routes, log

    def get(self, url, source, kind="json", retries=0):
        for k, v in self.routes.items():
            if k in url:
                if isinstance(v, Exception):
                    self.log.add(url=url, quelle=source, ok=False, ursache=v.cause)
                    raise v
                meta = {"url": url, "quelle": source, "abgerufen_utc": "2025-11-20T00:00:00+00:00", "sha256": "x", "ok": True}
                self.log.add(**meta)
                return (json.loads(json.dumps(v)) if kind == "json" else v), meta
        err = FetchError(source, "http_404_nicht_gefunden", url)
        self.log.add(url=url, quelle=source, ok=False, ursache=err.cause)
        raise err


def test_monitor_end_to_end(tmp_path, monkeypatch):
    """Zwei Läufe: Erstlauf legt Basis an (ohne Alarm), zweiter Lauf erkennt nur das Neue, Dubletten werden verworfen."""
    import scripts.research_monitor as rm
    from bii.research import report
    r = tmp_path / "research"
    for mod in (store, thesis, report):
        monkeypatch.setattr(mod, "R", r)
    monkeypatch.setattr(store, "FINDINGS", r / "findings.jsonl")
    monkeypatch.setattr(store, "EVIDENCE", r / "evidence")
    monkeypatch.setattr(store, "QUEUE", r / "queue")
    monkeypatch.setattr(report, "QUEUE", r / "queue")
    monkeypatch.setattr(store, "STATE", r / "state" / "monitor_status.json")
    monkeypatch.setattr(store, "ROOT", tmp_path)
    store.write_json(r / "universe.json", [{"ticker": "TST", "name": "Test Corp", "cik": "1",
                                             "ir_feeds": [{"name": "Test IR", "url": "https://ir.test/rss"}]}])
    today = __import__("datetime").date.today().isoformat()
    sub = {"cik": "1", "filings": {"recent": {"accessionNumber": ["0000000001-25-000002", "0000000001-25-000001"],
                                               "form": ["8-K", "10-Q"], "filingDate": [today, today],
                                               "primaryDocument": ["e.htm", "q.htm"], "items": ["2.02,9.01", ""],
                                               "reportDate": ["", "2025-09-30"], "acceptanceDateTime": ["", ""]}}}
    rss = f"""<rss><channel><item><title>Test Corp Reports Third Quarter Financial Results</title><link>https://ir.test/a</link>
              <pubDate>{__import__('email.utils').utils.format_datetime(__import__('datetime').datetime.now(__import__('datetime').timezone.utc))}</pubDate></item></channel></rss>"""
    routes = {"submissions": sub, "companyfacts": facts_fixture(), "index.json": {"directory": {"item": [{"name": "ex99-1.htm"}]}},
              "ex99-1.htm": "<p>Record revenue of $190.</p>", "q.htm": "<p>Quarterly report</p>", "ir.test/rss": rss,
              "yahoo": FetchError("Yahoo", "http_403_gesperrt", "y"), "stooq": FetchError("Stooq", "verbindung", "s")}

    def make_run(*a, **kw):
        run = rm.Run.__new__(rm.Run)
        rm.Run.__init__(run, None, False)
        run.client = FakeClient(routes, run.log)
        return run

    monkeypatch.setattr(sys, "argv", ["x", "--ohne-nachrichten"])
    real_run = rm.Run
    monkeypatch.setattr(rm, "Run", lambda t, news: _patched(real_run, t, news, routes))
    assert rm.main() == 0
    items = store.findings()
    assert {i["typ"] for i in items} >= {"einreichung", "neue_zahlen", "pressemitteilung"}
    assert all(i["quelle"].get("url") and i.get("erfasst_utc") is None and i.get("erstellt_utc") for i in items)
    assert not (r / "alert.txt").exists()                      # Erstlauf: kein Alarm
    queued = list((r / "queue").glob("*.json"))
    assert len(queued) == 2                                     # jüngster 10-Q + Ergebnis-8-K werden analysiert
    ev = [i for i in items if i.get("evidenz")]
    assert ev and (tmp_path / ev[0]["evidenz"]).read_text().startswith("QUELLE:")
    # Fehler je Quelle und Ursache getrennt gezählt
    fz = json.loads((r / "state" / "monitor_status.json").read_text())["fehlerzaehler"]
    assert fz["Kurs TST|kein_kurs"]["folge"] == 1

    # zweiter Lauf mit einer neuen 8-K → nur diese ist neu, Rest Dubletten; Alarm wegen Item 4.02
    sub["filings"]["recent"]["accessionNumber"].insert(0, "0000000001-25-000003")
    for k, v in (("form", "8-K"), ("filingDate", today), ("primaryDocument", "n.htm"), ("items", "4.02"),
                 ("reportDate", ""), ("acceptanceDateTime", "")):
        sub["filings"]["recent"][k].insert(0, v)
    assert rm.main() == 0
    new = store.findings()[len(items):]
    assert [n["typ"] for n in new] == ["einreichung"] and new[0]["wichtigkeit"]["wert"] == 1.0
    assert (r / "alert.txt").exists()
    assert store.verify_findings()[0]
    assert fz is not None and json.loads((r / "state" / "monitor_status.json").read_text())["fehlerzaehler"]["Kurs TST|kein_kurs"]["folge"] == 2


def _patched(real_run, tickers, news, routes):
    run = real_run(tickers, news)
    run.client = FakeClient(routes, run.log)
    return run
