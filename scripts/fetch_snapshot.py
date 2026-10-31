"""Daten-Schnappschuss für die Strategieforschung (läuft in GitHub Actions mit Internetzugang).

Speichert unter data/snapshots/:
- ff_10ind_monthly.csv      Kenneth R. French: 10 Industry Portfolios, wertgewichtet, Monatsrenditen in %
- ff_factors_monthly.csv    Kenneth R. French: Fama/French 3 Factors (Mkt-RF, SMB, HML, RF) in %
- etf_monthly.csv           Yahoo: bereinigte Monatsschlusskurse ausgewählter ETFs (USD)
- source_probe.json         Erreichbarkeit möglicher weiterer Datenquellen
- manifest.json             Quelle, Abrufzeit, SHA-256 je Datei
"""
from __future__ import annotations

import hashlib
import io
import json
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "snapshots"
UA = {"User-Agent": "Mozilla/5.0 (personal research; github.com/berdanates200333-code/berdan-investment-intelligence)"}
FF = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
ETFS = ["SPY", "XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY", "EFA", "EEM", "IEF", "AGG", "GLD"]
PROBES = {
    "ishares_nav_eunl": "https://www.ishares.com/de/privatanleger/de/produkte/251882/",
    "onvista_api": "https://api.onvista.de/api/v1/instruments/FUND/ISIN:IE00B4L5Y983/snapshot",
    "boerse_frankfurt": "https://www.boerse-frankfurt.de/etf/ie00b4l5y983",
    "ecb_fx": "https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A?format=csvdata&lastNObservations=1",
    "stooq": "https://stooq.com/q/d/l/?s=eunl.de&i=d",
    "fred": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DTB3",
    "sec_edgar": "https://data.sec.gov/submissions/CIK0001045810.json",
}


def ff_table(zip_name: str) -> pd.DataFrame:
    """Erste Monatstabelle (Zeilen mit JJJJMM) aus einer French-CSV-ZIP lesen."""
    r = requests.get(FF + zip_name, headers=UA, timeout=60)
    r.raise_for_status()
    z = zipfile.ZipFile(io.BytesIO(r.content))
    text = z.read(z.namelist()[0]).decode("latin-1")
    header, rows, started = None, [], False
    for line in text.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if not started:
            if len(parts) > 2 and parts[0] == "" and header is None:
                header = parts[1:]
            if parts[0].isdigit() and len(parts[0]) == 6:
                started = True
            else:
                continue
        if not (parts[0].isdigit() and len(parts[0]) == 6):
            break
        rows.append(parts)
    df = pd.DataFrame([r[1:] for r in rows], index=[r[0] for r in rows], columns=header).astype(float)
    df.index = pd.PeriodIndex([f"{i[:4]}-{i[4:]}" for i in df.index], freq="M").to_timestamp()
    df.index.name = "Date"
    if (df <= -99).any().any():
        raise ValueError(f"{zip_name}: Platzhalter -99.99 in Daten")
    return df


def yahoo_monthly(sym: str) -> pd.Series:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=max&interval=1mo"
    res = requests.get(url, headers=UA, timeout=30).json()["chart"]["result"][0]
    ts = pd.to_datetime(res["timestamp"], unit="s", utc=True).tz_localize(None).normalize()
    s = pd.Series(res["indicators"]["adjclose"][0]["adjclose"], index=ts, dtype=float, name=sym)
    s.index = s.index.to_period("M").to_timestamp()
    return s[~s.index.duplicated(keep="last")].dropna()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    manifest = {"abgerufen_utc": now, "dateien": {}}

    def save(df, name, source, note=""):
        p = OUT / name
        df.to_csv(p)
        manifest["dateien"][name] = {"quelle": source, "zeilen": len(df), "von": str(df.index[0].date()),
                                     "bis": str(df.index[-1].date()), "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                                     "hinweis": note}

    save(ff_table("10_Industry_Portfolios_CSV.zip"), "ff_10ind_monthly.csv", FF + "10_Industry_Portfolios_CSV.zip",
         "Average Value Weighted Returns -- Monthly, Prozent")
    save(ff_table("F-F_Research_Data_Factors_CSV.zip"), "ff_factors_monthly.csv", FF + "F-F_Research_Data_Factors_CSV.zip",
         "Monatlich, Prozent; RF = 1-Monats-T-Bill")
    etf, errs = {}, {}
    for s in ETFS:
        try:
            etf[s] = yahoo_monthly(s)
        except Exception as e:  # noqa: BLE001
            errs[s] = str(e)[:200]
    if etf:
        df = pd.DataFrame(etf)
        df = df[df.index < pd.Timestamp.now().to_period("M").to_timestamp()]  # laufenden Monat entfernen
        save(df, "etf_monthly.csv", "Yahoo Finance chart API (inoffiziell), adjclose, interval=1mo",
             f"USD, Monatsanfang-Stempel = Monatsschluss dieses Monats; Fehler: {errs}")
    probe = {}
    for k, u in PROBES.items():
        try:
            r = requests.get(u, headers=UA, timeout=20)
            probe[k] = {"status": r.status_code, "bytes": len(r.content), "typ": r.headers.get("content-type", "")[:60]}
        except Exception as e:  # noqa: BLE001
            probe[k] = {"fehler": str(e)[:150]}
    (OUT / "source_probe.json").write_text(json.dumps(probe, indent=2))
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    print(json.dumps(probe, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
