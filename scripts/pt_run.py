"""Täglicher Paper-Trading-Lauf (nur virtuell). Aufruf: python scripts/pt_run.py [version]"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from bii import journal  # noqa: E402
from bii.papertrading import engine, report  # noqa: E402
from bii.papertrading import rules_v1_0 as rules  # noqa: E402
from bii.papertrading.data import Provider  # noqa: E402

PT = ROOT / "papertrading"


def _jsonl(path: Path) -> list:
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()] if path.exists() else []


def effective_end() -> str:
    ext = _jsonl(PT / "verlaengerung.jsonl")
    return ext[-1]["neues_ende"] if ext else rules.END


def main() -> int:
    vdir = PT / f"v{rules.VERSION}"
    vdir.mkdir(parents=True, exist_ok=True)
    sp = vdir / "state.json"
    state = json.loads(sp.read_text()) if sp.exists() else engine.new_state(rules)
    freig = json.loads((PT / "freigabe.json").read_text()) if (PT / "freigabe.json").exists() else []
    vetos = _jsonl(PT / "review" / "vetos.jsonl")
    now = datetime.now(timezone.utc)
    summ = engine.run(state, Provider(), rules, vdir / "journal.jsonl", now=now, vetos=vetos, freigaben=freig, ende=effective_end())
    sp.write_text(json.dumps(state, indent=1, ensure_ascii=False, sort_keys=True))
    pd.DataFrame(state["equity"]).to_csv(vdir / "equity.csv", index=False)
    pd.DataFrame(state["closed"]).to_csv(vdir / "trades.csv", index=False)
    (PT / "ops_status.json").write_text(json.dumps({"letzter_lauf_utc": now.isoformat(timespec="seconds"),
        "letzter_erfolg_utc": now.isoformat(timespec="seconds") if summ["verarbeitet"] and not summ["probleme"] else None,
        "letzter_handelstag": state["last_date"], "probleme": summ["probleme"][:20]}, indent=1, ensure_ascii=False))
    ok, msg = journal.verify(vdir / "journal.jsonl")
    m = report.metrics(state)
    (ROOT / "reports" / "papertrading").mkdir(parents=True, exist_ok=True)
    (ROOT / "reports" / "papertrading" / "latest.md").write_text(
        f"# Paper-Trading v{rules.VERSION} – Tagesstand\n\nStand: {now:%Y-%m-%d %H:%M} UTC · letzter verarbeiteter Handelstag: {state['last_date']}\n\n"
        f"- Aktiv: {m['aktiv_eur']:.2f} € ({m['rendite_aktiv']*100:+.2f} %) · Benchmark: {m['bench_eur']:.2f} € ({m['rendite_bench']*100:+.2f} %)\n"
        f"- Offene Positionen: {m['trades_offen']} · abgeschlossen: {m['trades_abgeschlossen']} · Pause: {'JA' if state['paused'] else 'nein'}\n"
        f"- Journal-Kette: {'intakt' if ok else 'FEHLER: ' + msg}\n- Datenprobleme dieses Laufs: {len(summ['probleme'])}\n" + "".join(f"  - {p}\n" for p in summ["probleme"][:10]))
    print(json.dumps({"verarbeitet": summ["verarbeitet"], "probleme": summ["probleme"][:10], "journal": msg}, ensure_ascii=False))
    # Jeder Daten-/Integritätsfehler ist ein fehlgeschlagener Lauf, kein grüner Erfolg.
    return 2 if summ["probleme"] or not ok else 0


if __name__ == "__main__":
    raise SystemExit(main())
