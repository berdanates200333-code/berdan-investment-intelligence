"""Systemprobelauf der KI-Konten (identischer Orderpfad wie im Wettbewerb, aber getrennte Konten forecast/probelauf/<ki>/).
Beweist: Datenstufe A -> Order dokumentiert -> Ausführung in der Folgesitzung über die gemeinsame Engine, für beide Konten identisch.
Kein Teil des Wettbewerbs. Aufruf täglich nach Börsenschluss."""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bii.forecast import ai_portfolio as ap, calendars, live, universe  # noqa: E402


def main() -> int:
    now = datetime.now(timezone.utc)
    lv = live.Live(now, "2y")
    u = universe.load()
    insts = {i["yahoo"]: i for i in u["stufe1_handelbar"] + u["benchmarks"]}
    day = calendars.last_complete_session("XNYS", now)
    start = str(day.date())
    root = ROOT / "forecast" / "probelauf"
    rules = ap.make_rules(start, "2099-12-31", ("SPY",), version="PROBELAUF")
    rules.REGIME = "SPY"
    rc = 0
    for ki in ("claude", "chatgpt"):
        st = ap.load_state(ki, rules, root=root)
        prov = ap.EngineProvider(lv, insts)
        res = ap.run_cycle(ki, st, prov, rules, now=now, root=root)
        if st["last_date"] and not st["positions"] and not st["pending"] and not st["closed"] and not st["failed"]:
            q = lv.get(insts["SPY"])
            fx = prov.fx()
            if q is not None and fx is not None:
                try:
                    entry = float(q.df.loc[day, "close"])
                    ap.submit_order(ki, st, rules, "PROBELAUF:SPY", round(entry * 1.01, 2), round(entry * 0.97, 2), round(entry * 1.06, 2), float(fx.iloc[-1]), q, now=now, root=root, allowed={"SPY"}, probelauf=True)
                except Exception as e:  # noqa: BLE001
                    print(ki, "Order nicht angenommen:", e)
        ap.save_state(ki, st, root=root)
        print(ki, {"verarbeitet": res["verarbeitet"], "probleme": res["probleme"][:5], "pending": len(st["pending"]), "positionen": list(st["positions"]), "closed": len(st["closed"])})
        rc = rc or (2 if any("Pflichtdaten" in p for p in res["probleme"]) else 0)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
