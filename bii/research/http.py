"""Höflicher HTTP-Client mit Protokoll je Abruf.

- SEC EDGAR verlangt einen deklarierten User-Agent und max. 10 Anfragen/Sekunde
  (https://www.sec.gov/os/accessing-edgar-data). Wir bleiben deutlich darunter (≈4/s).
- Jeder Abruf wird mit URL, Status, Zeitpunkt, Größe und SHA-256 protokolliert (FetchLog),
  Fehler getrennt nach Quelle und Ursache.
"""
from __future__ import annotations

import hashlib
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

import requests

DEFAULT_UA = ("berdan-investment-intelligence research-prototype "
              "(+https://github.com/berdanates200333-code/berdan-investment-intelligence)")
TIMEOUT = 30


def user_agent() -> str:
    # In GitHub Actions über die Repository-Variable SEC_USER_AGENT setzbar (kein Geheimnis).
    return os.environ.get("SEC_USER_AGENT") or DEFAULT_UA


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def classify_error(exc: Exception | None, status: int | None) -> str:
    """Fehlerursache als stabile Kategorie (für Zähler je Quelle und Ursache)."""
    if status is not None:
        if status == 403:
            return "http_403_gesperrt"
        if status == 404:
            return "http_404_nicht_gefunden"
        if status == 429:
            return "http_429_ratenlimit"
        if status >= 500:
            return "http_5xx_server"
        return f"http_{status}"
    if isinstance(exc, requests.Timeout):
        return "zeitueberschreitung"
    if isinstance(exc, requests.ConnectionError):
        return "verbindung"
    if isinstance(exc, ValueError):
        return "format"
    return type(exc).__name__ if exc else "unbekannt"


@dataclass
class FetchLog:
    entries: list[dict] = field(default_factory=list)

    def add(self, **kw) -> None:
        self.entries.append(kw)

    def errors(self) -> list[dict]:
        return [e for e in self.entries if not e.get("ok")]


class Client:
    def __init__(self, log: FetchLog | None = None, min_interval: float = 0.25):
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": user_agent(), "Accept-Encoding": "gzip, deflate"})
        self.log = log or FetchLog()
        self.min_interval = min_interval
        self._last = 0.0

    def get(self, url: str, source: str, *, kind: str = "json", retries: int = 2):
        """kind: json | text | bytes. Gibt (daten, meta) zurück oder wirft nach Protokollierung."""
        last_exc, status = None, None
        for attempt in range(retries + 1):
            wait = self.min_interval - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()
            try:
                r = self.s.get(url, timeout=TIMEOUT)
                status = r.status_code
                if status == 429 or status >= 500:
                    raise requests.HTTPError(f"HTTP {status}")
                if status != 200:
                    break
                body = r.content
                meta = {"url": url, "quelle": source, "status": status, "abgerufen_utc": now_utc(),
                        "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest(), "ok": True}
                data = r.json() if kind == "json" else r.text if kind == "text" else body
                self.log.add(**meta)
                return data, meta
            except Exception as e:  # noqa: BLE001 – wird protokolliert und klassifiziert
                last_exc = e
                if status not in (429,) and not (status and status >= 500) and not isinstance(
                        e, (requests.Timeout, requests.ConnectionError)):
                    break
                time.sleep(1.5 * (attempt + 1))
        cause = classify_error(last_exc if status in (None, 200) else None, None if status in (None, 200) else status)
        self.log.add(url=url, quelle=source, status=status, abgerufen_utc=now_utc(), ok=False, ursache=cause,
                     detail=str(last_exc)[:200] if last_exc else None)
        raise FetchError(source, cause, url)


class FetchError(RuntimeError):
    def __init__(self, source: str, cause: str, url: str):
        super().__init__(f"{source}: {cause} ({url})")
        self.source, self.cause, self.url = source, cause, url
