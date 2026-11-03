"""Risikolabor (reproduzierbar, nur Auswertung): lädt 5 Jahre Tagesdaten + EZB-FX und simuliert 1/2/3 % Risiko je Trade in 5 Marktphasen."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pandas as pd  # noqa: E402

from bii.forecast import live, risikolabor as rl  # noqa: E402
from bii.papertrading import rules_v1_0 as base  # noqa: E402
from bii.papertrading.data import ecb_eurusd  # noqa: E402

now = datetime.now(timezone.utc)
lv = live.Live(now, "5y")
frames = {}
for s in (*base.UNIVERSE, "SPY"):
    q = lv.get({"yahoo": s, "venue": "XNYS", "waehrung": "USD", "klasse": "aktien_etf" if s == "SPY" else "aktie"})
    if q is None or q.df.empty:
        print("Daten fehlen:", s); sys.exit(2)
    frames[s] = q.df
fx = ecb_eurusd("2021-06-01")
fx.index = pd.DatetimeIndex(fx.index)
phases = [p for p in rl.PHASEN if len(sys.argv) < 2 or p[0].split()[0] in sys.argv[1:]]
res = {}
for name, a, b in phases:
    res[name] = [rl.run_window(frames, fx, a, b, lvl, base.UNIVERSE) for lvl in rl.LEVELS]
    print(name, [(round(r["rendite_pct"], 1), round(r["maxdd_pct"], 1), r["trades"]) for r in res[name]], flush=True)
out = ROOT / "reports" / "risikolabor"
out.mkdir(parents=True, exist_ok=True)
(out / "ergebnis.json").write_text(json.dumps({"erstellt_utc": now.isoformat(timespec="seconds"), "ergebnisse": res}, indent=1, ensure_ascii=False))
(out / "ergebnis.md").write_text(rl.markdown(res))
print((out / "ergebnis.md").read_text())
