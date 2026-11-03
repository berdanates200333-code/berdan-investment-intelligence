"""Startbedingungen prüfen und dokumentieren. 'python scripts/fc_gate.py' schreibt forecast/wettbewerb_gate.json (Status nicht_gestartet).
Start nur explizit: 'python scripts/fc_gate.py --start' (verweigert, solange Bedingungen fehlen)."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bii.forecast import gate  # noqa: E402

if "--start-solo" in sys.argv:
    from bii.forecast import ai_portfolio as ap, wettbewerb
    from bii import journal
    now = datetime.now(timezone.utc)
    doc = gate.start_solo(now)
    (ROOT / "forecast" / "wettbewerb.json").write_text(json.dumps(doc, indent=1, ensure_ascii=False))
    rules = ap.make_rules(doc["start"], doc["ende_exklusiv"], (), version=doc["experiment"])
    st = ap.load_state("claude", rules)
    ap.save_state("claude", st)                       # persistenter Kontostand 10.000 €
    journal.append({"typ": "konto_eroeffnet", "ki": "claude", "kapital_eur": 10000, "start": doc["start"], "ende_exklusiv": doc["ende_exklusiv"],
                    "benchmark": doc["benchmark_instrument"]["yahoo"], "version": doc["experiment"]}, path=ap.account_dir("claude") / "handel.jsonl", now=now)
    print("SOLO GESTARTET: Start", doc["start"], "Eröffnung", doc["start_eroeffnung_utc"], "Ende (exkl.)", doc["ende_exklusiv"])
elif "--solo-check" in sys.argv:
    for k, v in gate.solo_checks(datetime.now(timezone.utc)).items():
        print(("OK   " if v["ok"] else "FEHLT"), k, "-", v["detail"])
elif "--start" in sys.argv:
    doc = gate.start(datetime.now(timezone.utc))
    (ROOT / "forecast" / "wettbewerb.json").write_text(json.dumps(doc, indent=1, ensure_ascii=False))
    print("GESTARTET", doc["start"])
else:
    g = gate.evaluate_gate()
    (ROOT / "forecast" / "wettbewerb_gate.json").write_text(json.dumps({"status": "nicht_gestartet" if not g["alle_erfuellt"] else "startbereit", **g}, indent=1, ensure_ascii=False))
    for k, v in g["bedingungen"].items():
        print(("OK   " if v["ok"] else "FEHLT"), k, "-", v["detail"])
