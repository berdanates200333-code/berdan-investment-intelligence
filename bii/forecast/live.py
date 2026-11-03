"""Live-Datenabruf mit Zweitquelle und Qualitätsstufen (Yahoo primär; Nasdaq/Stooq sekundär). Rohantworten werden per SHA-256 protokolliert."""
from __future__ import annotations

import hashlib
import io
from datetime import datetime, timezone

import pandas as pd
import requests

from . import calendars, quality

UA = {"User-Agent": "Mozilla/5.0 (Berdan personal paper research)"}


class Live:
    def __init__(self, now: datetime | None = None, range_: str = "5y"):
        self.now = pd.Timestamp(now or datetime.now(timezone.utc))
        self.range, self.cache, self.log, self.requests = range_, {}, [], []

    def _get(self, url):
        r = requests.get(url, headers=UA, timeout=25)
        self.requests.append({"url": url.split("?")[0], "status": r.status_code, "sha256": hashlib.sha256(r.content).hexdigest(),
                              "abgerufen_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")})
        r.raise_for_status()
        return r

    def _yahoo(self, sym, venue):
        j = self._get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range={self.range}&interval=1d&events=div%2Csplits").json()["chart"]["result"][0]
        m = j["meta"]
        q = j["indicators"]["quote"][0]
        tz = m.get("exchangeTimezoneName", "UTC")
        idx = pd.to_datetime(j["timestamp"], unit="s", utc=True).tz_convert(tz).normalize().tz_localize(None)
        df = pd.DataFrame({k: q[k] for k in ("open", "high", "low", "close", "volume")}, index=idx, dtype=float)
        df = df[~df.index.duplicated(keep="last")].dropna(subset=["close"])
        last = calendars.last_complete_session(venue, self.now)
        df = df.loc[:last]                       # unvollständige/vorläufige Balken nie verwenden
        meta = {"symbol_abweichend": m.get("symbol") != sym, "waehrung": m.get("currency"), "zeitzone": tz, "boerse": m.get("exchangeName"), "typ": m.get("instrumentType")}
        return df, meta, j.get("events", {})

    def _nasdaq(self, sym, last):
        kind = "etf" if sym in ("SPY", "QQQ", "IWM", "GLD", "IAU", "EFA") else "stocks"
        start = (last - pd.Timedelta(days=400)).strftime("%Y-%m-%d")
        js = self._get(f"https://api.nasdaq.com/api/quote/{sym}/historical?assetclass={kind}&fromdate={start}&todate={last:%Y-%m-%d}&limit=400").json()
        rows = js["data"]["tradesTable"]["rows"]
        f = lambda x: float(str(x).replace("$", "").replace(",", ""))  # noqa: E731
        return {pd.Timestamp(datetime.strptime(r["date"], "%m/%d/%Y").date()): {k: f(r[k]) for k in ("open", "high", "low", "close")} for r in rows}

    def _stooq(self, sym):
        s = sym.lower() if sym.startswith("^") else sym.lower() + ".us"
        df = pd.read_csv(io.StringIO(self._get(f"https://stooq.com/q/d/l/?s={s}&i=d").text))
        if "Close" not in df.columns:
            raise ValueError("Stooq-Antwort unbrauchbar")
        return {pd.Timestamp(r.Date): {"open": r.Open, "high": r.High, "low": r.Low, "close": r.Close} for r in df.itertuples()}

    def _stockanalysis(self, sym):
        """Unabhängige Zweitquelle für Xetra-Titel (S&P Global via StockAnalysis): Tabelle Datum/Open/High/Low/Close/..."""
        from html.parser import HTMLParser

        class T(HTMLParser):
            def __init__(self):
                super().__init__(); self.rows, self.row, self.cell, self.on = [], [], None, False
            def handle_starttag(self, tag, attrs):
                self.on = self.on or tag == "table"
                if self.on and tag == "tr": self.row = []
                if self.on and tag in ("td", "th"): self.cell = ""
            def handle_data(self, d):
                if self.cell is not None: self.cell += d
            def handle_endtag(self, tag):
                if tag in ("td", "th") and self.cell is not None: self.row.append(self.cell.strip()); self.cell = None
                if tag == "tr" and self.row: self.rows.append(self.row)
        txt = self._get(f"https://stockanalysis.com/quote/etr/{sym.split('.')[0]}/history/").text
        if f"ETR:{sym.split('.')[0]}" not in txt:
            raise ValueError("Identität nicht bestätigt")
        t = T(); t.feed(txt); out = {}
        for r in t.rows:
            if len(r) < 5 or r[0] == "Date":
                continue
            try:
                out[pd.Timestamp(datetime.strptime(r[0], "%b %d, %Y"))] = {k: float(r[i].replace(",", "")) for i, k in enumerate(("open", "high", "low", "close"), 1)}
            except ValueError:
                continue
        if not out:
            raise ValueError("keine Zeilen")
        return out

    def get(self, instrument: dict) -> quality.QualData | None:
        sym, venue = instrument["yahoo"], calendars.venue_of(instrument)
        if sym in self.cache:
            return self.cache[sym]
        qd = None
        try:
            df, meta, ev = self._yahoo(sym, venue)
            klasse = instrument.get("klasse") or ("index" if sym.startswith("^") else "aktie")
            tier, reasons = quality.check_frame(df, venue, self.now, instrument.get("waehrung"), meta, klasse)
            qd = quality.QualData(sym, venue, df, tier, reasons, actions=ev, meta=meta, klasse=klasse)
            if tier != quality.C:
                chain = [("StockAnalysis", lambda: self._stockanalysis(sym))] if venue == "XETR" else [("Nasdaq", lambda: self._nasdaq(sym, df.index[-1])), ("Stooq", lambda: self._stooq(sym))]
                for name, fn in chain:
                    if name == "Nasdaq" and sym.startswith("^"):
                        continue
                    try:
                        qd.secondary, qd.secondary_name = fn(), name
                        break
                    except Exception as e:  # noqa: BLE001
                        self.log.append(f"{sym}: Zweitquelle {name} nicht nutzbar ({type(e).__name__})")
        except Exception as e:  # noqa: BLE001
            self.log.append(f"{sym}: Abruf fehlgeschlagen ({type(e).__name__})")
        self.cache[sym] = qd
        return qd
