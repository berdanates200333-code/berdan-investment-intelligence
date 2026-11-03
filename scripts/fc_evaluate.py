"""Automatische Erfolgskontrolle (täglich per GitHub Actions). Bewertet fällige Prognosen aller KIs und schreibt
bewertungen.jsonl + Datenstatus. Arbeitet nur mit Kursdaten – liest keine Analysen/Gründe der KIs.
Aufruf: python scripts/fc_evaluate.py [--datenstatus]"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bii import journal  # noqa: E402
from bii.forecast import evaluate, jr  # noqa: E402
from bii.papertrading.data import check_bars, stooq_close, yahoo_ohlcv  # noqa: E402


class Live:
    def __init__(self):
        self.cache, self.log = {}, []

    def closes(self, sym):
        if sym not in self.cache:
            try:
                df = yahoo_ohlcv(sym, "1y")
                probs = check_bars(df)
                self.log += [f"{sym}: {p}" for p in probs]
                s = df["close"]
                try:   # Gegenprüfung des letzten Kurses mit Stooq (falls erreichbar)
                    z = stooq_close(sym.lower().replace("^", "^") if sym.startswith("^") else sym.lower() + ".us")
                    d = s.index[-1]
                    if d in z.index and abs(s.iloc[-1] / z.loc[d] - 1) > 0.01:
                        self.log.append(f"{sym}: Quellenabweichung Yahoo/Stooq > 1 % am {d.date()}")
                except Exception:  # noqa: BLE001
                    self.log.append(f"Hinweis {sym}: Zweitquelle Stooq nicht erreichbar (einquellig)")
                self.cache[sym] = s
            except Exception as e:  # noqa: BLE001
                self.log.append(f"{sym}: Abruf fehlgeschlagen ({type(e).__name__})")
                self.cache[sym] = None
        return self.cache[sym]


def main() -> int:
    now = datetime.now(timezone.utc)
    live = Live()
    syms = sorted({p["instrument"]["yahoo"] for ki in jr.KIS for p in journal.read(jr.path(ki))})
    n_new = 0
    for ki in jr.KIS:
        n_new += len(evaluate.evaluate_ki(ki, live.closes, now.date(), now))
    status = {"lauf_utc": now.isoformat(timespec="seconds"), "neue_bewertungen": n_new, "instrumente": {}, "probleme": live.log}
    for s in syms:
        c = live.closes(s)
        status["instrumente"][s] = None if c is None else {"letzter_kurs": round(float(c.iloc[-1]), 4), "datum": str(c.index[-1].date())}
    (ROOT / "reports" / "forecast").mkdir(parents=True, exist_ok=True)
    (ROOT / "forecast" / "ops_status.json").write_text(json.dumps(status, indent=1, ensure_ascii=False))
    ok = all(v is not None for v in status["instrumente"].values())
    print(json.dumps(status, ensure_ascii=False)[:1500])
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
