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
    # unabhängiger Plausibilitäts-Proxy (CoinGecko-ID), Prüfung über stabiles Kursverhältnis
    proxy_coingecko: str | None = None
    asset_class: str = "equity_etf"


# Prüfstufen (v1.2): nur ein unabhängiger Anbieter mit demselben Instrument "bestätigt" einen Kurs.
STUFE = {"unabhaengig": "bestaetigt", "handelsplatz": "plausibel", "proxy": "plausibel"}

# Beobachtungsuniversum Phase 1 (liquide, für deutsche Privatanleger handelbar)
UNIVERSE = [
    Instrument("WORLD", "iShares Core MSCI World UCITS ETF (Acc)", "IE00B4L5Y983", "Xetra", "EUR",
               yahoo="EUNL.DE", stooq="eunl.de", alt_venues=("EUNL.F", "EUNL.DU", "EUNL.MU", "EUNL.SG")),
    Instrument("SP500", "iShares Core S&P 500 UCITS ETF (Acc)", "IE00B5BMR087", "Xetra", "EUR",
               yahoo="SXR8.DE", stooq="sxr8.de", alt_venues=("SXR8.F", "SXR8.DU", "SXR8.MU", "SXR8.SG")),
    Instrument("GOLD", "Xetra-Gold (physisch hinterlegte Inhaberschuldverschreibung)", "DE000A0S9GB0", "Xetra", "EUR",
               yahoo="4GLD.DE", stooq="4gld.de", asset_class="gold_etc",
               alt_venues=("4GLD.F", "4GLD.DU", "4GLD.MU", "4GLD.SG"), proxy_coingecko="pax-gold"),
    Instrument("BTC", "Bitcoin", None, "Spot (Referenzkurs)", "EUR",
               yahoo="BTC-EUR", coingecko="bitcoin", asset_class="crypto"),
    Instrument("ETH", "Ethereum", None, "Spot (Referenzkurs)", "EUR",
               yahoo="ETH-EUR", coingecko="ethereum", asset_class="crypto"),
]


@dataclass
class PriceSeries:
    instrument: Instrument
    close: pd.Series                      # Tagesschluss, Index = Datum (Europe/Berlin)
    source: str
    fetched_at: str
    cross_check: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    secondary: pd.Series | None = None    # Zweitquelle für datumsgenaue Prüfung
    secondary_name: str | None = None
    secondary_kind: str | None = None     # "unabhaengig" | "handelsplatz" | "proxy"
    tolerance: float = 0.015

    @property
    def last_date(self):
        return self.close.index[-1]

    @property
    def last(self) -> float:
        return float(self.close.iloc[-1])

    def verify(self, date) -> dict:
        """Datumsgenaue Gegenprüfung eines Schlusskurses.
        direkt (unabhängig/Handelsplatz): |Primär/Zweit - 1| <= Toleranz am selben Datum.
        proxy (z. B. Xetra-Gold vs. tokenisiertes Gold): Verhältnis Primär/Proxy am Datum weicht
        höchstens um die Toleranz vom Median der 60 vorherigen gemeinsamen Tage ab."""
        date = pd.Timestamp(date)
        base = {"datum": str(date.date()), "quelle": self.secondary_name, "art": self.secondary_kind}
        if date not in self.close.index:
            return {**base, "ok": False, "grund": "Primärquelle ohne Kurs an diesem Datum"}
        if self.secondary is None or self.secondary.empty:
            return {**base, "ok": False, "grund": "keine Zweitquelle verfügbar"}
        if date not in self.secondary.index:
            return {**base, "ok": False, "grund": "Zweitquelle ohne Kurs an diesem Datum"}
        if self.secondary_kind == "proxy":
            common = self.close.index.intersection(self.secondary.index)
            ratio = (self.close.loc[common] / self.secondary.loc[common])
            ref = ratio[ratio.index < date].tail(60)
            if len(ref) < 20:
                return {**base, "ok": False, "grund": "zu wenig Vergleichshistorie für Proxy-Prüfung"}
            dev = abs(ratio.loc[date] / ref.median() - 1)
        else:
            dev = abs(self.close.loc[date] / self.secondary.loc[date] - 1)
        ok = bool(dev <= self.tolerance)
        out = {**base, "ok": ok, "abweichung": round(float(dev), 5),
               "stufe": STUFE.get(self.secondary_kind, "plausibel"),
               "grund": None if ok else f"Abweichung {dev*100:.2f} % > Toleranz {self.tolerance*100:.1f} %"}
        if self.secondary_kind == "proxy":
            out["hinweis"] = "Proxy prüft die Kursbewegung (Verhältnis), nicht das Kursniveau"
        return out

    def complete(self, now_utc: pd.Timestamp | None = None) -> pd.Series:
        """Nur abgeschlossene, endgültige Tagesbalken (v1.2).
        Krypto: Tagesbalken = UTC-Kalendertag; der laufende UTC-Tag wird verworfen.
        Xetra-Instrumente: ein Tagesschluss zählt erst ab dem FOLGETAG (Berlin), damit kein vorläufiger
        Kurs kurz nach Handelsschluss als Signal- oder Ausführungskurs dient (T+1-Bestätigung)."""
        now_utc = now_utc or pd.Timestamp.now(tz="UTC")
        if self.instrument.asset_class == "crypto":
            cutoff = now_utc.tz_convert("UTC").normalize().tz_localize(None)
            return self.close[self.close.index < cutoff]
        today = now_utc.tz_convert("Europe/Berlin").normalize().tz_localize(None)
        return self.close[self.close.index < today]


def _yahoo(symbol: str, rng: str = "2y") -> pd.Series:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range={rng}&interval=1d"
    j = requests.get(url, headers=UA, timeout=TIMEOUT).json()
    res = j["chart"]["result"][0]
    ts = pd.to_datetime(res["timestamp"], unit="s", utc=True)
    # adjclose berücksichtigt Splits/Ausschüttungen (bei thesaurierenden ETFs identisch)
    ind = res["indicators"]
    vals = ind.get("adjclose", [{}])[0].get("adjclose") or ind["quote"][0]["close"]
    tz = "UTC" if res.get("meta", {}).get("instrumentType") == "CRYPTOCURRENCY" else "Europe/Berlin"
    s = pd.Series(vals, index=ts.tz_convert(tz).normalize().tz_localize(None), dtype=float)
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
    """CoinGecko liefert tägliche Punkte um 00:00 UTC (= Schlusskurs des VORTAGS) plus einen
    aktuellen Punkt. Wir ordnen 00:00-Punkte dem Vortag zu und verwerfen den laufenden Punkt."""
    url = f"https://api.coingecko.com/api/v3/coins/{coin}/market_chart?vs_currency={vs}&days={days}&interval=daily"
    j = requests.get(url, headers=UA, timeout=TIMEOUT).json()
    df = pd.DataFrame(j["prices"], columns=["t", "p"])
    ts = pd.to_datetime(df["t"], unit="ms", utc=True).dt.tz_localize(None)
    midnight = ts == ts.dt.normalize()
    idx = (ts[midnight].dt.normalize() - pd.Timedelta(days=1))
    s = pd.Series(df.loc[midnight, "p"].values, index=idx.values)
    s = s[~s.index.duplicated(keep="last")].sort_index()
    s.attrs["currency"] = vs.upper()
    return s


def ecb_eurusd() -> tuple[float, str]:
    url = "https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A?format=csvdata&lastNObservations=1"
    df = pd.read_csv(io.StringIO(requests.get(url, headers=UA, timeout=TIMEOUT).text))
    return float(df["OBS_VALUE"].iloc[-1]), str(df["TIME_PERIOD"].iloc[-1])


TOLERANCE = {"unabhaengig": 0.015, "handelsplatz": 0.025, "proxy": 0.025}


def fetch(inst: Instrument) -> PriceSeries:
    """Primärquelle + eine Zweitquelle für datumsgenaue Prüfung.
    Reihenfolge der Zweitquellen: unabhängige Anbieter (Stooq, CoinGecko), gleiche ISIN an
    anderem Handelsplatz (eingeschränkt unabhängig), unabhängiger Proxy (Verhältnisprüfung)."""
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    primary, src, errors = None, None, []
    candidates = [("Yahoo Finance", _yahoo, inst.yahoo, "unabhaengig"), ("Stooq", _stooq, inst.stooq, "unabhaengig"),
                  ("CoinGecko", _coingecko, inst.coingecko, "unabhaengig")]
    candidates += [(f"Yahoo {v} (anderer Handelsplatz)", _yahoo, v, "handelsplatz") for v in inst.alt_venues]
    candidates += [(f"CoinGecko {inst.proxy_coingecko} (Proxy)", _coingecko, inst.proxy_coingecko, "proxy")]
    for name, fn, arg, kind in candidates:
        if not arg:
            continue
        try:
            s = fn(arg)
            if len(s) < 50:
                raise ValueError("zu wenige Datenpunkte")
            cur = s.attrs.get("currency")
            if cur and cur != inst.currency:
                raise ValueError(f"Währung {cur} statt {inst.currency}")
            if primary is None:
                primary, src = s, name
                continue
            ps = PriceSeries(inst, primary, src, now, secondary=s, secondary_name=name,
                             secondary_kind=kind, tolerance=TOLERANCE[kind])
            common = primary.index.intersection(s.index)
            if not len(common):
                raise ValueError("kein gemeinsames Datum")
            v = ps.verify(common[-1])
            if "abweichung" not in v:
                raise ValueError(v["grund"])
            return _finish(ps, {**v, "unabhaengig": kind == "unabhaengig"}, errors)
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
    jumps = ps.close.pct_change().abs().tail(10)
    if (jumps > 0.35).any():
        ps.warnings.append(f"Unplausibler Tagessprung am {jumps.idxmax().date()} – Datenprüfung erforderlich.")
    return ps
