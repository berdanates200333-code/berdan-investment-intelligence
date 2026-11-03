"""Benchmark-Entscheidung EINMALIG festschreiben (vor Wettbewerbsstart). Kandidaten in Präferenzreihenfolge aus forecast/universum.json.
Wählt den ersten Kandidaten mit Datenstufe A (Zweitquelle, Identität, Währung, Handelsplatz, keine Kapitalmaßnahme im Fenster).
Existiert die Entscheidung bereits, wird sie NIE überschrieben."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bii.forecast import live, quality, universe  # noqa: E402

F = ROOT / "forecast" / "benchmark_entscheidung.json"
if F.exists():
    print("Benchmark bereits festgeschrieben:", json.loads(F.read_text())["symbol"])
    raise SystemExit(0)
now = datetime.now(timezone.utc)
lv = live.Live(now, "2y")
u = universe.load()
tests = []
for b in u["benchmarks"]:
    q = lv.get(b)
    t = q.tier_at(q.df.index[-1]) if q is not None else quality.C
    tests.append({"symbol": b["yahoo"], "waehrung": b["waehrung"], "stufe": t, "zweitquelle": getattr(q, "secondary_name", None), "gruende": getattr(q, "reasons", ["keine Daten"])})
    if t == quality.A:
        F.write_text(json.dumps({"symbol": b["yahoo"], "waehrung": b["waehrung"], "venue": b["venue"], "festgeschrieben_utc": now.isoformat(timespec="seconds"),
                                 "regel": u["benchmark_regel"], "tests": tests}, indent=1, ensure_ascii=False))
        print("FESTGESCHRIEBEN:", b["yahoo"], b["waehrung"])
        break
else:
    print("KEIN Kandidat mit Datenstufe A:", tests)
    raise SystemExit(2)
