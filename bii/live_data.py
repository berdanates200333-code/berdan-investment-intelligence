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
    asset_class: str = "equity_etf"


# Beobachtungsuniversum Phase 1 (liquide, für deutsche Privatanleger handelbar)
UNIVERSE = [
    Instrument("WORLD", "iShares Core MSCI World UCITS ETF (Acc)", "IE00B4L5Y983", "Xetra", "EUR",
               yahoo="EUNL.DE", stooq="eunl.de"),
    Instrument("SP500", "iShares Core S&P 500 UCITS ETF (Acc)", "IE00B5BMR087", "Xetra", "EUR",
               yahoo="SXR8.DE", stooq="sxr8.de"),
    Instrument("GOLD", "Xetra-Gold (physisch hinterlegte Inhaberschuldverschreibung)", "DE000A0S9GB0", "Xetra", "EUR",
               yahoo="4GLD.DE", stooq="4gld.de", asset_class="gold_etc"),
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
    return s[~s.index.duplicated(keep="last")].dropna()


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


def fetch(inst: Instrument, tolerance: float = 0.015) -> PriceSeries:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    primary, src, errors = None, None, []
    for name, fn, arg in (("Yahoo Finance", _yahoo, inst.yahoo), ("Stooq", _stooq, inst.stooq),
                          ("CoinGecko", _coingecko, inst.coingecko)):
        if not arg:
            continue
        try:
            s = fn(arg)
            if len(s) < 50:
                raise ValueError("zu wenige Datenpunkte")
            if primary is None:
                primary, src = s, name
            else:
                # Gegenprüfung am letzten gemeinsamen Datum
                common = primary.index.intersection(s.index)
                if len(common):
                    d = common[-1]
                    dev = abs(primary[d] / s[d] - 1)
                    ps = PriceSeries(inst, primary, src, now)
                    return _finish(ps, {"quelle": name, "datum": str(d.date()), "abweichung": round(float(dev), 5),
                                        "ok": bool(dev <= tolerance)}, errors)
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
