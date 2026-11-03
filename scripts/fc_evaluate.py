"""Automatische Erfolgskontrolle (täglich per GitHub Actions). Bewertet fällige Prognosen aller KIs mit qualitätsgeprüften Kursdaten
(nur Kursdaten, liest keine Gründe/Analysen der KIs). Aufruf: python scripts/fc_evaluate.py"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bii import journal  # noqa: E402
from bii.forecast import evaluate, jr, live, quality  # noqa: E402


def main() -> int:
    now = datetime.now(timezone.utc)
    lv = live.Live(now)
    insts = {}
    for ki in jr.KIS:
        for p in journal.read(jr.path(ki)):
            insts[p["instrument"]["yahoo"]] = p["instrument"]
    n_new = sum(len(evaluate.evaluate_ki(ki, lv.get, now.date(), now)) for ki in jr.KIS)
    status = {"lauf_utc": now.isoformat(timespec="seconds"), "neue_bewertungen": n_new, "instrumente": {}, "probleme": lv.log, "abrufe": lv.requests}
    bad = 0
    for sym, inst in insts.items():
        q = lv.get(inst)
        if q is None:
            status["instrumente"][sym] = {"stufe": quality.C, "grund": "keine Daten"}
            bad += 1
            continue
        t = q.tier_at(q.df.index[-1])
        status["instrumente"][sym] = {"stufe": t, "letzter_kurs": round(float(q.df.close.iloc[-1]), 4), "datum": str(q.df.index[-1].date()),
                                      "zweitquelle": q.secondary_name, "gruende": q.reasons}
        bad += t == "C_unzulaessig"
    (ROOT / "forecast" / "ops_status.json").write_text(json.dumps(status, indent=1, ensure_ascii=False))
    print(json.dumps({k: v for k, v in status.items() if k != "abrufe"}, ensure_ascii=False)[:1500])
    return 2 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
