"""Wochenbericht (und ab 25.01.2027 einmalig die Abschlussbewertung). Aufruf: python scripts/pt_weekly_report.py"""
from __future__ import annotations

import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bii import journal  # noqa: E402
from bii.papertrading import report  # noqa: E402
from bii.papertrading import rules_v1_0 as rules  # noqa: E402


def main() -> int:
    vdir = ROOT / "papertrading" / f"v{rules.VERSION}"
    if not (vdir / "state.json").exists():
        print("Noch kein Zustand – kein Bericht.")
        return 0
    state = json.loads((vdir / "state.json").read_text())
    entries = journal.read(vdir / "journal.jsonl")
    today = datetime.now(timezone.utc).date()
    out = ROOT / "reports" / "papertrading"
    (out / "weekly").mkdir(parents=True, exist_ok=True)
    iso = today.isocalendar()
    txt = report.weekly_report(state, entries, today, rules.VERSION)
    (out / "weekly" / f"{iso.year}-W{iso.week:02d}.md").write_text(txt)
    (out / "weekly" / "latest.md").write_text(txt)
    ext_path = ROOT / "papertrading" / "verlaengerung.jsonl"
    ext = [json.loads(x) for x in ext_path.read_text().splitlines() if x.strip()] if ext_path.exists() else []
    end = date.fromisoformat(ext[-1]["neues_ende"] if ext else rules.END)
    if today > end:
        txt_final = report.final_evaluation(state, today, end, rules.VERSION)
        (out / "abschluss.md").write_text(txt_final)
        if "Urteil: VERLÄNGERN" in txt_final:   # vorab festgelegte Regel: Stichprobe zu klein -> um 4 Wochen verlängern
            new_end = (end + timedelta(weeks=report.EXTENSION_WEEKS)).isoformat()
            with ext_path.open("a") as f:
                f.write(json.dumps({"datum": today.isoformat(), "altes_ende": end.isoformat(), "neues_ende": new_end,
                                    "grund": "Stichprobe unzureichend (Regel aus Strategiedokument), Regeln unverändert"}, ensure_ascii=False) + "\n")
    print(txt.splitlines()[2] if len(txt.splitlines()) > 2 else "ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
