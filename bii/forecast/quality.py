"""Datenqualitätsstufen. Unzulässige Daten werden NICHT bewertet und NICHT ausgeführt (kein bloßer Hinweis in der Statistik).

Stufe A  "A_bestaetigt"   : gültige Balken, Identität/Währung/Handelsplatz stimmen, Balken ist aktuell und endgültig,
                             zweite unabhängige Quelle bestätigt den Balken (O/H/L/C je <= Toleranz).
Stufe B  "B_einquellig"   : gültige Balken, aber keine bestätigende Zweitquelle für diesen Tag.
Stufe C  "C_unzulaessig"  : ungültig (OHLC inkonsistent, nichtendlich, fehlende Handelstage, veraltet, Sprung > 40 %,
                             Identität/Währung falsch) ODER Zweitquelle weicht ab.
Zulässigkeit: Wettbewerb und virtuelle Ausführung verlangen A. Der Pilot (vor Wettbewerbsstart) lässt B zu, gekennzeichnet.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import calendars

A, B, C = "A_bestaetigt", "B_einquellig", "C_unzulaessig"
RANK = {A: 2, B: 1, C: 0}
# Zweck- und instrumentbezogene Toleranzen für die Zweitquellen-Bestätigung (statt pauschal 2 %):
# Der offizielle Schlusskurs ist bei allen Anbietern praktisch identisch -> enge Grenze. Open/High/Low hängen von Handelsplatz-/Tape-Definition ab -> weitere Grenze.
TOL_CLOSE = {"aktie": 0.005, "aktien_etf": 0.003, "gold": 0.003, "index": 0.003, "krypto": 0.010}
TOL_OHL = {"aktie": 0.015, "aktien_etf": 0.008, "gold": 0.008, "index": 0.008, "krypto": 0.020}
EXPECTED_TYPE = {"aktie": "EQUITY", "aktien_etf": "ETF", "gold": "ETF", "index": "INDEX", "krypto": "CRYPTOCURRENCY"}
SPLIT_WINDOW = pd.Timedelta(days=30)     # Kapitalmaßnahme (Split) im Fenster -> Preisdefinitionen zwischen Anbietern nicht vergleichbar -> Stufe C
MIN_TIER = {"wettbewerb": A, "ausfuehrung": A, "pilot": B}
TZ = {"XNYS": "America/New_York", "XETR": "Europe/Berlin", "CRYPTO": "UTC"}


@dataclass
class QualData:
    symbol: str
    venue: str
    df: pd.DataFrame
    frame_tier: str
    reasons: list = field(default_factory=list)
    secondary: dict = field(default_factory=dict)      # Datum -> {open, high, low, close}
    secondary_name: str | None = None
    actions: dict = field(default_factory=dict)        # Kapitalmaßnahmen (Splits/Dividenden) laut Quelle
    meta: dict = field(default_factory=dict)
    klasse: str = "aktie"

    def split_near(self, d) -> bool:
        d = pd.Timestamp(d)
        for raw in (self.actions or {}).get("splits", {}).values():
            ts = pd.Timestamp(raw["date"], unit="s").normalize()
            if abs(ts - d) <= SPLIT_WINDOW:
                return True
        return False

    def tier_at(self, d) -> str:
        if self.frame_tier == C:
            return C
        d = pd.Timestamp(d)
        if d not in self.df.index or self.split_near(d):
            return C
        s = self.secondary.get(d)
        if s is None:
            return B
        row = self.df.loc[d]
        dc = abs(float(row["close"]) / s["close"] - 1) if s.get("close") else 1.0
        dohl = max((abs(float(row[k]) / s[k] - 1) for k in ("open", "high", "low") if s.get(k)), default=0.0)
        return A if dc <= TOL_CLOSE[self.klasse] and dohl <= TOL_OHL[self.klasse] else C

    def allowed(self, d, phase: str) -> tuple[bool, str]:
        t = self.tier_at(d)
        return RANK[t] >= RANK[MIN_TIER[phase]], t


def check_frame(df: pd.DataFrame, venue: str, now, expected_currency=None, meta=None, klasse: str | None = None) -> tuple[str, list]:
    """Prüft einen Kursrahmen (nur abgeschlossene Balken). Rückgabe (Stufe, Gründe)."""
    reasons = []
    meta = meta or {}
    if df is None or df.empty:
        return C, ["keine Daten"]
    if df.index.has_duplicates or not df.index.is_monotonic_increasing:
        reasons.append("doppelte/unsortierte Balken")
    vals = df[["open", "high", "low", "close", "volume"]].to_numpy(dtype=float)
    if not np.isfinite(vals).all():
        reasons.append("nichtendliche Werte")
    elif (vals[:, :4] <= 0).any():
        reasons.append("nichtpositive Kurse")
    else:
        bad = (df.high < df[["open", "low", "close"]].max(axis=1) - 1e-6) | (df.low > df[["open", "high", "close"]].min(axis=1) + 1e-6)
        if bad.tail(250).any():
            reasons.append("inkonsistente OHLC-Balken")
        if (df.close.pct_change().abs().tail(250) > 0.4).any():
            reasons.append("Kurssprung > 40 % (Split-/Datenfehler?)")
    if meta.get("symbol_abweichend"):
        reasons.append("Symbol-Identität weicht ab")
    if expected_currency and meta.get("waehrung") and meta["waehrung"] != expected_currency:
        reasons.append(f"Währung {meta['waehrung']} statt {expected_currency}")
    if klasse and meta.get("typ") and meta["typ"] != EXPECTED_TYPE[klasse]:
        reasons.append(f"Instrumententyp {meta['typ']} statt {EXPECTED_TYPE[klasse]}")
    if meta.get("zeitzone") and meta["zeitzone"] != TZ[venue]:
        reasons.append(f"Handelsplatz/Zeitzone {meta['zeitzone']} passt nicht zu {venue}")
    try:
        last = calendars.last_complete_session(venue, now)
        if df.index[-1] < last:
            reasons.append(f"veraltet: letzter Balken {df.index[-1].date()}, erwartet {last.date()}")
        if venue != "CRYPTO":
            import exchange_calendars as xc
            req = xc.get_calendar(venue).sessions_in_range(df.index[max(0, len(df) - 60)], min(df.index[-1], last))
            miss = req.difference(df.index)
            if len(miss):
                reasons.append(f"{len(miss)} Handelstage fehlen (z. B. {miss[0].date()})")
    except Exception as e:  # noqa: BLE001
        reasons.append(f"Kalenderprüfung fehlgeschlagen ({type(e).__name__})")
    return (C if reasons else B), reasons
