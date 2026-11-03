"""Börsenkalender je Handelsplatz (exchange_calendars): Sommerzeit, Feiertage, verkürzte Handelstage.

Venues: XNYS (US-Aktien/ETFs, auch SPY/GLD), XETR (Xetra), CRYPTO (24/7, Tagesbalken = UTC-Kalendertag, Abschluss 00:00 UTC).
Es gibt KEINE feste Eröffnungszeit: Öffnung/Schluss kommen aus dem Kalender des jeweiligen Handelsplatzes.
"""
from __future__ import annotations

import exchange_calendars as xc
import pandas as pd

VENUES = ("XNYS", "XETR", "CRYPTO")
BAR_SETTLE = pd.Timedelta(minutes=45)      # Balken gilt erst 45 min nach Handelsschluss als endgültig
INDEX_VENUE = {"^GSPC": "XNYS", "^IXIC": "XNYS", "^DJI": "XNYS", "^RUT": "XNYS"}


def venue_of(instrument: dict) -> str:
    v = instrument.get("venue") or INDEX_VENUE.get(instrument.get("yahoo", "")) or INDEX_VENUE.get(instrument.get("id", ""))
    if v not in VENUES:
        raise ValueError(f"Handelsplatz unbekannt/ungültig für {instrument.get('id')}: {v}")
    return v


def _cal(venue):
    return xc.get_calendar(venue)


def sessions_after(venue: str, ref, n: int) -> pd.Timestamp:
    """n-ter Handelstag NACH ref (ref = Datum, nicht notwendig Handelstag)."""
    ref = pd.Timestamp(ref).normalize()
    if venue == "CRYPTO":
        return ref + pd.Timedelta(days=n)
    c = _cal(venue)
    rng = c.sessions_in_range(ref + pd.Timedelta(days=1), ref + pd.Timedelta(days=n * 2 + 14))
    return pd.Timestamp(rng[n - 1])


def is_session(venue: str, d) -> bool:
    return True if venue == "CRYPTO" else bool(_cal(venue).is_session(pd.Timestamp(d).normalize()))


def session_open(venue: str, d) -> pd.Timestamp:
    d = pd.Timestamp(d).normalize()
    return d.tz_localize("UTC") if venue == "CRYPTO" else pd.Timestamp(_cal(venue).session_open(d))


def session_close(venue: str, d) -> pd.Timestamp:
    d = pd.Timestamp(d).normalize()
    return (d + pd.Timedelta(days=1)).tz_localize("UTC") if venue == "CRYPTO" else pd.Timestamp(_cal(venue).session_close(d))


def last_complete_session(venue: str, now) -> pd.Timestamp:
    """Letzter Handelstag, dessen Tagesbalken bei 'now' endgültig ist (Schluss + 45 min)."""
    now = pd.Timestamp(now).tz_convert("UTC")
    if venue == "CRYPTO":
        return now.tz_localize(None).normalize() - pd.Timedelta(days=1) if now >= now.normalize() + BAR_SETTLE else now.tz_localize(None).normalize() - pd.Timedelta(days=2)
    c = _cal(venue)
    for d in reversed(c.sessions_in_range((now - pd.Timedelta(days=14)).tz_localize(None).normalize(), now.tz_localize(None).normalize())):
        if c.session_close(d) + BAR_SETTLE <= now:
            return pd.Timestamp(d)
    raise ValueError("kein abgeschlossener Handelstag gefunden")


def next_session_open(venue: str, now) -> tuple[pd.Timestamp, pd.Timestamp]:
    """(Datum, Öffnungszeit UTC) der ersten Handelssitzung, die nach 'now' beginnt."""
    now = pd.Timestamp(now).tz_convert("UTC")
    d = now.tz_localize(None).normalize()
    for i in range(0, 15):
        day = d + pd.Timedelta(days=i)
        if is_session(venue, day) and session_open(venue, day) > now:
            return day, session_open(venue, day)
    raise ValueError("keine kommende Sitzung")


def forecast_deadline_ok(venue: str, first_target_session, created_utc) -> bool:
    """Prognose muss vor Beginn der ersten bewerteten Sitzung (Eröffnung des 1-Tages-Zieltags) dokumentiert sein."""
    return pd.Timestamp(created_utc).tz_convert("UTC") < session_open(venue, first_target_session)


def horizon_dates(venue: str, ref_date, horizons=(1, 5, 20)) -> dict:
    return {str(h): str(sessions_after(venue, ref_date, h).date()) for h in horizons}
