"""Datenzugriff für das Paper-Trading: Tageskurse (OHLCV) mit Gegenprüfung, EUR/USD, Nachrichten-Check.

Nur kostenlose Quellen (Yahoo Finance inoffiziell, Stooq, EZB, Google News RSS). Alles verzögerte Tagesdaten,
KEINE Echtzeit- oder Intraday-Daten -> Intraday-Handel ist ausgeschlossen. Ausfälle werden protokolliert
(Datenqualität), nie stillschweigend ersetzt.
"""
from __future__ import annotations

import io
import re

import pandas as pd
import requests

UA = {"User-Agent": "Mozilla/5.0 (personal research script)"}
TIMEOUT = 25


def yahoo_ohlcv(symbol: str, rng: str = "2y") -> pd.DataFrame:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range={rng}&interval=1d"
    res = requests.get(url, headers=UA, timeout=TIMEOUT).json()["chart"]["result"][0]
    tz = res["meta"].get("exchangeTimezoneName", "UTC")
    q = res["indicators"]["quote"][0]
    idx = pd.to_datetime(res["timestamp"], unit="s", utc=True).tz_convert(tz).normalize().tz_localize(None)
    df = pd.DataFrame({k: q[k] for k in ("open", "high", "low", "close", "volume")}, index=idx).astype(float)
    df = df[~df.index.duplicated(keep="last")].dropna()
    df.attrs["currency"] = res["meta"].get("currency")
    return df


def stooq_close(symbol: str) -> pd.Series:
    txt = requests.get(f"https://stooq.com/q/d/l/?s={symbol}&i=d", headers=UA, timeout=TIMEOUT).text
    df = pd.read_csv(io.StringIO(txt))
    if "Close" not in df.columns:
        raise ValueError("Stooq: unerwartete Antwort")
    return df.set_index(pd.to_datetime(df["Date"]))["Close"].astype(float)


def ecb_eurusd(start: str = "2026-09-01") -> pd.Series:
    """USD je 1 EUR (EZB-Referenzkurs, ~16 Uhr MEZ des Tages)."""
    url = f"https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A?format=csvdata&startPeriod={start}"
    df = pd.read_csv(io.StringIO(requests.get(url, headers=UA, timeout=TIMEOUT).text))
    return pd.Series(df["OBS_VALUE"].values, index=pd.to_datetime(df["TIME_PERIOD"]), dtype=float)


def check_bars(df: pd.DataFrame) -> list[str]:
    """Plausibilitätsprüfung der Balken (Konsistenz, Sprünge, Alter)."""
    problems = []
    bad = (df["high"] < df[["open", "close", "low"]].max(axis=1) - 1e-9) | (df["low"] > df[["open", "close", "high"]].min(axis=1) + 1e-9)
    if bad.tail(60).any():
        problems.append("inkonsistente OHLC-Balken in den letzten 60 Tagen")
    if (df["close"].pct_change().abs().tail(30) > 0.4).any():
        problems.append("unplausibler Kurssprung > 40 % (Split-/Datenfehler?)")
    if (df["volume"].tail(20) <= 0).any():
        problems.append("Volumen 0 in den letzten 20 Tagen")
    return problems


class Provider:
    """Lädt Daten einmal je Lauf. Für Tests kann eine Unterklasse die Methoden überschreiben."""

    def __init__(self):
        self.cache: dict[str, pd.DataFrame] = {}
        self.log: list[str] = []          # Datenprobleme dieses Laufs

    def ohlcv(self, symbol: str) -> pd.DataFrame | None:
        if symbol not in self.cache:
            try:
                df = yahoo_ohlcv(symbol)
                problems = check_bars(df)
                for problem in problems:
                    self.log.append(f"{symbol}: {problem}")
                self.cache[symbol] = None if problems else df
            except Exception as e:  # noqa: BLE001 - Ausfälle werden protokolliert
                self.log.append(f"{symbol}: Yahoo-Abruf fehlgeschlagen ({type(e).__name__})")
                self.cache[symbol] = None
        return self.cache[symbol]

    def fx(self) -> pd.Series | None:
        try:
            return ecb_eurusd()
        except Exception as e:  # noqa: BLE001
            self.log.append(f"EZB EUR/USD fehlgeschlagen ({type(e).__name__})")
        try:
            return yahoo_ohlcv("EURUSD=X", "6mo")["close"]
        except Exception as e:  # noqa: BLE001
            self.log.append(f"EUR/USD-Ersatzquelle fehlgeschlagen ({type(e).__name__})")
            return None

    def crosscheck(self, symbol: str, date, close: float, tol: float) -> dict:
        """Zweitquelle Stooq für den Schlusskurs am Entscheidungstag. status: bestaetigt|abweichend|ungeprueft."""
        try:
            s = stooq_close(f"{symbol.lower()}.us" if "." not in symbol else symbol.lower())
            ts = pd.Timestamp(date)
            if ts not in s.index:
                return {"status": "ungeprueft", "grund": "Stooq ohne Kurs an diesem Datum"}
            dev = abs(close / float(s.loc[ts]) - 1)
            return {"status": "bestaetigt" if dev <= tol else "abweichend", "abweichung": round(dev, 5), "quelle": "Stooq"}
        except Exception as e:  # noqa: BLE001
            return {"status": "ungeprueft", "grund": f"Stooq nicht verfügbar ({type(e).__name__})"}

    def news(self, symbol: str, days: int, neg_words: tuple) -> dict:
        """Schlagzeilen der letzten Tage (Google News RSS, Sekundärquelle). Negativ-Schlagwort = Veto-Hinweis."""
        try:
            from ..research import feeds
            items = feeds.google_news(f"{symbol} stock", days=days)
        except Exception as e:  # noqa: BLE001
            return {"status": "ungeprueft", "grund": f"Nachrichtenabruf fehlgeschlagen ({type(e).__name__})", "treffer": []}
        hits = [i["titel"] for i in items if any(re.search(r"\b" + re.escape(w), i["titel"], re.I) for w in neg_words)]
        return {"status": "geprueft", "anzahl": len(items), "treffer": hits[:5],
                "quellen": [i.get("url") or i.get("quelle_url") for i in items[:3]]}
