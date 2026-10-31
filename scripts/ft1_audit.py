"""Prüfung des FT1-Regelwerks auf veraltete Daten und unbeabsichtigte virtuelle Ausführungen.

NUR LESEND: lädt aktuelle Kurse, schreibt aber weder Journal noch Portfolio-Zustand.
Ausgabe: reports/ft1_audit.md
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bii import forward, journal  # noqa: E402
from bii.live_data import UNIVERSE, fetch  # noqa: E402


def main(now_utc: pd.Timestamp | None = None) -> int:
    now_utc = now_utc or pd.Timestamp.now(tz="UTC")
    state = json.loads(forward.STATE.read_text())
    entries = journal.read()
    L = [f"# FT1-Prüfung (nur lesend) – {now_utc.tz_convert('Europe/Berlin'):%d.%m.%Y %H:%M} Uhr Berlin", "",
         "Diese Prüfung ändert weder Journal noch Portfolio-Zustand.", "", "## 1. Signale auf ungeprüfter Datenbasis"]
    for e in entries:
        if e.get("typ") != "signal":
            continue
        d = e.get("daten", {})
        checked = bool(d.get("monatsschluss_pruefung") or (d.get("gegenpruefung") or {}).get("ok"))
        L.append(f"- Eintrag {e['seq']} `{e['signal_id']}` ({e['aktion']}, Regelwerk {e.get('regel_version') or '1.0'}): "
                 + ("Kurs gegengeprüft" if checked else "**ohne Gegenprüfung erzeugt** – " + "; ".join(d.get("warnungen", []))[:160]))
    L += ["", "## 2. Offene Orders gegen den neuesten abgeschlossenen Monat"]
    month = forward.last_completed_month(now_utc)
    series = {}
    for inst in UNIVERSE:
        try:
            series[inst.key] = fetch(inst)
        except Exception as ex:  # noqa: BLE001
            L.append(f"- {inst.key}: keine Daten ({str(ex)[:100]})")
    for o in state.get("pending", []):
        ps = series.get(o["asset"])
        sig_month = o["signal_id"].split("-", 3)[-1]
        line = f"- `{o['signal_id']}` {o['aktion']} {o['asset']} (Signalmonat {sig_month})"
        if ps is None:
            L.append(line + ": keine Kursdaten")
            continue
        chk = forward.month_check(ps, now_utc)
        sig = forward.trend_signal(ps.complete(now_utc), month) if chk["ok"] else None
        if sig is None:
            L.append(line + f": Monat {month} noch nicht auswertbar ({chk.get('grund')})")
            continue
        newer = "KAUF/halten" if sig["investiert"] else "VERKAUF"
        conflict = (o["aktion"] == "KAUF") != sig["investiert"]
        L.append(line + f": Monat {month} ergäbe **{newer}** (Abstand zur 12M-SMA {sig['abstand_zur_sma']*100:+.1f} %) – "
                 + ("**WIDERSPRUCH: Ausführung würde sofort ein Gegensignal erzeugen (doppelte Kosten)**" if conflict
                    else "kein Widerspruch"))
    L += ["", "## 3. Manuelle Workflow-Starts",
          "Bis Phase 2 lief jeder manuelle Start („Run workflow“) produktiv: Signale bekamen das Startdatum als Signaldatum. "
          "Bei Bitcoin (täglicher Handel) verschiebt das den Ausführungstag. Seit Phase 2 sind manuelle Starts standardmäßig "
          "Probeläufe ohne Journal-/Zustandsänderung (Eingabe `produktiv` nötig)."]
    out = ROOT / "reports" / "ft1_audit.md"
    out.write_text("\n".join(L) + "\n")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit(main())
