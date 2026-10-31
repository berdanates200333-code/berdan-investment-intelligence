"""Abruf aktueller Tageskurse aus kostenlosen Quellen mit Gegenprüfung.

Alle Quellen liefern VERZÖGERTE bzw. Tagesschlusskurse – keine Echtzeitdaten.
Jede Zeitreihe trägt Metadaten (Quelle, Abrufzeit, letzter Zeitstempel, Währung).

Hinweis zu Nutzungsbedingungen: Yahoo-Finance-Endpunkte sind inoffiziell und nur für
private, nicht-kommerzielle Auswertung gedacht; sie können ohne Vorwarnung ausfallen.
Deshalb werden immer zweite Quellen geprüft (Stooq, CoinGecko, EZB).
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field
from datetime import datetime, timezone

import pandas as pd
import requests

UA = {"User-Agent": "Mozilla/5.0 (personal research script)"}
TIMEOUT = 20


@dataclass
class Instrument:
    key: str
    name: str
    isin: str | None
    venue: str
    currency: str
    yahoo: str | None = None
    stooq: str | None = None
    coingecko: str | None = None
    # gleiche ISIN an anderen deutschen Handelsplätzen (Yahoo-Kürzel) – nur eingeschränkt unabhängig
    alt_venues: tuple = ()
    asset_class: str = "equity_etf"


# Beobachtungsuniversum Phase 1 (liquide, für deutsche Privatanleger handelbar)
UNIVERSE = [
    Instrument("WORLD", "iShares Core MSCI World UCITS ETF (Acc)", "IE00B4L5Y983", "Xetra", "EUR",
               yahoo="EUNL.DE", stooq="eunl.de", alt_venues=("EUNL.F", "EUNL.DU", "EUNL.MU", "EUNL.SG")),
    Instrument("SP500", "iShares Core S&P 500 UCITS ETF (Acc)", "IE00B5BMR087", "Xetra", "EUR",
               yahoo="SXR8.DE", stooq="sxr8.de", alt_venues=("SXR8.F", "SXR8.DU", "SXR8.MU", "SXR8.SG")),
    Instrument("GOLD", "Xetra-Gold (physisch hinterlegte Inhaberschuldverschreibung)", "DE000A0S9GB0", "Xetra", "EUR",
               yahoo="4GLD.DE", stooq="4gld.de", asset_class="gold_etc",
               alt_venues=("4GLD.F", "4GLD.DU", "4GLD.MU", "4GLD.SG")),
    Instrument("BTC", "Bitcoin", None, "Spot (Referenzkurs)", "EUR",
               yahoo="BTC-EUR", coingecko="bitcoin", asset_class="crypto"),
    Instrument("ETH", "Ethereum", None, "Spot (Referenzkurs)", "EUR",
               yahoo="ETH-EUR", coingecko="ethereum", asset_class="crypto"),
]


@dataclass
class PriceSeries:
    instrument: Instrument
    close: pd.Series                      # Tagesschluss, Index = Datum
    source: str
    fetched_at: str
    cross_check: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    @property
    def last_date(self):
        return self.close.index[-1]

    @property
    def last(self) -> float:
        return float(self.close.iloc[-1])


def _yahoo(symbol: str, rng: str = "2y") -> pd.Series:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range={rng}&interval=1d"
    j = requests.get(url, headers=UA, timeout=TIMEOUT).json()
    res = j["chart"]["result"][0]
    ts = pd.to_datetime(res["timestamp"], unit="s", utc=True)
    # adjclose berücksichtigt Splits/Ausschüttungen (bei thesaurierenden ETFs identisch)
    ind = res["indicators"]
    vals = ind.get("adjclose", [{}])[0].get("adjclose") or ind["quote"][0]["close"]
    s = pd.Series(vals, index=ts.tz_convert("Europe/Berlin").normalize().tz_localize(None), dtype=float)
    s = s[~s.index.duplicated(keep="last")].dropna()
    s.attrs["currency"] = res.get("meta", {}).get("currency")
    return s


def _stooq(symbol: str) -> pd.Series:
    url = f"https://stooq.com/q/d/l/?s={symbol}&i=d"
    txt = requests.get(url, headers=UA, timeout=TIMEOUT).text
    df = pd.read_csv(io.StringIO(txt))
    if "Close" not in df.columns:
        raise ValueError(f"Stooq: unerwartete Antwort für {symbol}")
    return df.set_index(pd.to_datetime(df["Date"]))["Close"].astype(float)


def _coingecko(coin: str, vs: str = "eur", days: int = 365) -> pd.Series:
    url = f"https://api.coingecko.com/api/v3/coins/{coin}/market_chart?vs_currency={vs}&days={days}&interval=daily"
    j = requests.get(url, headers=UA, timeout=TIMEOUT).json()
    df = pd.DataFrame(j["prices"], columns=["t", "p"])
    idx = pd.to_datetime(df["t"], unit="ms", utc=True).dt.tz_localize(None).dt.normalize()
    s = pd.Series(df["p"].values, index=idx)
    return s[~s.index.duplicated(keep="last")]


def ecb_eurusd() -> tuple[float, str]:
    url = "https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A?format=csvdata&lastNObservations=1"
    df = pd.read_csv(io.StringIO(requests.get(url, headers=UA, timeout=TIMEOUT).text))
    return float(df["OBS_VALUE"].iloc[-1]), str(df["TIME_PERIOD"].iloc[-1])


def fetch(inst: Instrument, tolerance: float = 0.015, venue_tolerance: float = 0.025) -> PriceSeries:
    """Primärquelle + Gegenprüfung. Reihenfolge der Zweitquellen: unabhängige Anbieter
    (Stooq, CoinGecko), danach gleiche ISIN an anderem Handelsplatz (nur eingeschränkt unabhängig)."""
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    primary, src, errors = None, None, []
    candidates = [("Yahoo Finance", _yahoo, inst.yahoo, True), ("Stooq", _stooq, inst.stooq, True),
                  ("CoinGecko", _coingecko, inst.coingecko, True)]
    candidates += [(f"Yahoo {v} (anderer Handelsplatz)", _yahoo, v, False) for v in inst.alt_venues]
    for name, fn, arg, independent in candidates:
        if not arg:
            continue
        try:
            s = fn(arg)
            if len(s) < 50 and primary is None:
                raise ValueError("zu wenige Datenpunkte")
            cur = s.attrs.get("currency")
            if cur and cur != inst.currency:
                raise ValueError(f"Währung {cur} statt {inst.currency}")
            if primary is None:
                primary, src = s, name
                continue
            common = primary.index.intersection(s.index)
            if not len(common):
                raise ValueError("kein gemeinsames Datum")
            d = common[-1]
            dev = abs(primary[d] / s[d] - 1)
            tol = tolerance if independent else venue_tolerance
            return _finish(PriceSeries(inst, primary, src, now),
                           {"quelle": name, "datum": str(d.date()), "abweichung": round(float(dev), 5),
                            "ok": bool(dev <= tol), "unabhaengig": independent}, errors)
        except Exception as e:  # noqa: BLE001 - Quellen dürfen ausfallen, wird protokolliert
            errors.append(f"{name}: {type(e).__name__}: {e}"[:200])
    if primary is None:
        raise RuntimeError(f"{inst.key}: keine Datenquelle erreichbar ({'; '.join(errors)})")
    return _finish(PriceSeries(inst, primary, src, now), {}, errors)


def _finish(ps: PriceSeries, cc: dict, errors: list[str]) -> PriceSeries:
    ps.cross_check = cc
    ps.warnings.extend(errors)
    if not cc:
        ps.warnings.append("Keine unabhängige Zweitquelle verfügbar – Kurs ungeprüft.")
    elif not cc["ok"]:
        ps.warnings.append(f"Quellenabweichung {cc['abweichung']*100:.2f} % > Toleranz – Datenprüfung erforderlich.")
    age = (pd.Timestamp.now().normalize() - ps.last_date).days
    limit = 2 if ps.instrument.asset_class == "crypto" else 4
    if age > limit:
        ps.warnings.append(f"Letzter Kurs ist {age} Tage alt ({ps.last_date.date()}).")
    jumps = ps.close.pct_change().abs()
    if (jumps > 0.35).any():
        ps.warnings.append(f"Unplausibler Tagessprung am {jumps.idxmax().date()} – Datenprüfung erforderlich.")
    return ps
