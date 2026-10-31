"""Täglicher Marktcheck: Daten holen, prüfen, Forward-Test fortschreiben, Kurzbericht schreiben.

Aufruf:  python scripts/daily_check.py
Ausgabe: reports/latest.md, reports/daily/JJJJ-MM-TT.md, journal/journal.jsonl (append-only)
Exit-Code 0 auch bei Datenproblemen (werden im Bericht ausgewiesen).
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bii import forward, journal  # noqa: E402
from bii.live_data import UNIVERSE, fetch  # noqa: E402
from bii.risk import RiskRules, drawdown_status  # noqa: E402

BERLIN = ZoneInfo("Europe/Berlin")
MOVE_ALERT = {"equity_etf": 0.03, "gold_etc": 0.03, "crypto": 0.08}


def main() -> int:
    now = datetime.now(BERLIN)
    today = pd.Timestamp(now.date())
    series, failures = {}, {}
    for inst in UNIVERSE:
        try:
            series[inst.key] = fetch(inst)
        except Exception as e:  # noqa: BLE001
            failures[inst.key] = str(e)[:300]

    lines = [f"# Claude Market Briefing – {now:%d.%m.%Y}",
             f"Erstellt {now:%d.%m.%Y %H:%M} Uhr (Europe/Berlin). Tagesschlusskurse, **keine Echtzeitdaten**.", ""]

    if not series:
        lines += ["**Datenprüfung erforderlich:** Keine Datenquelle erreichbar. Keine Handlung möglich.", ""]
        lines += [f"- {k}: {v}" for k, v in failures.items()]
        _write(lines, now)
        (ROOT / "reports" / "alert.txt").write_text("Datenausfall: keine Quelle erreichbar")
        return 0

    result = forward.step(series, today)
    rules = RiskRules()

    # Marktlage
    lines += ["## Gesamtlage", "| Instrument | Letzter Kurs | Datum | 1 Tag | 1 Monat | Trend (12M-SMA) | Datenqualität |",
              "|---|---|---|---|---|---|---|"]
    alerts = []
    for key, ps in series.items():
        c = ps.close
        d1 = c.iloc[-1] / c.iloc[-2] - 1
        m1 = c.iloc[-1] / c[c.index <= c.index[-1] - pd.Timedelta(days=30)].iloc[-1] - 1
        sig = forward.trend_signal(c, today)
        trend = "–" if sig is None else ("über SMA" if sig["investiert"] else "UNTER SMA") + f" ({sig['abstand_zur_sma']*100:+.1f} %)"
        cc = ps.cross_check
        if cc.get("ok"):
            mark = "✓" if cc.get("unabhaengig", True) else "≈"
            dq = f"{mark} {ps.source} vs. {cc['quelle']}: Δ {cc['abweichung']*100:.2f} %"
        elif cc:
            dq = f"⚠ Abweichung {cc['abweichung']*100:.2f} % zu {cc['quelle']} – Datenprüfung erforderlich"
        else:
            dq = f"⚠ nur {ps.source}, Zweitquelle ausgefallen"
        old_px = [w for w in ps.warnings if "Tage alt" in w or "Tagessprung" in w]
        if old_px:
            dq += " · " + "; ".join(old_px)
        lines.append(f"| {ps.instrument.name[:34]} | {ps.last:,.2f} {ps.instrument.currency} | {ps.last_date:%d.%m.} | "
                     f"{d1*100:+.1f} % | {m1*100:+.1f} % | {trend} | {dq} |")
        if abs(d1) >= MOVE_ALERT[ps.instrument.asset_class]:
            alerts.append(f"{key}: Tagesbewegung {d1*100:+.1f} %")
    for k, v in failures.items():
        lines.append(f"| {k} | – | – | – | – | – | ✗ nicht abrufbar |")
    lines += ["", "Legende Datenqualität: ✓ unabhängige Zweitquelle bestätigt · ≈ gleicher Anbieter, anderer Handelsplatz · ⚠ ungeprüft", ""]

    # Signale
    sigs = [e for e in result["events"] if e["typ"] == "signal" and e["aktion"] != "HALTEN"]
    execs = [e for e in result["events"] if e["typ"] == "ausfuehrung"]
    lines.append("## Handelsideen / Signale (Regelwerk FT1, virtuell)")
    if not sigs and not execs:
        lines.append("Keine neuen Signale. **Keine Handlung erforderlich.**")
    for e in sigs:
        d = e["daten"]
        why = ("Startkauf Buy & Hold (Vergleichsportfolio)" if e["portfolio"] == "BENCH" else
               f"Monatsschluss {d.get('monat')} {d.get('monatsschluss')} vs. 12M-SMA {d.get('sma12')}")
        lines.append(f"- **{e['aktion']} {e['asset']}** ({e['portfolio']}), Signal-ID `{e['signal_id']}`: {why}. "
                     f"Zielgewicht {e['zielgewicht']*100:.0f} %. Ausführung virtuell zum nächsten Tagesschluss.")
    for e in execs:
        lines.append(f"- Ausgeführt (virtuell): {e['aktion']} {e['asset']} ({e['portfolio']}) zu {e['kurs']} am {e['kursdatum']}.")
    if result["state"]["pending"]:
        lines.append(f"- Offene virtuelle Orders: {len(result['state']['pending'])}")
    lines.append("")

    # Portfolio
    lines += ["## Virtuelle Portfolios (Start je 10.000 €)", "| Portfolio | Wert | Rendite | Drawdown vom Hoch |", "|---|---|---|---|"]
    for p, v in result["valuation"].items():
        hist = [h["wert"] for h in result["state"]["portfolios"][p]["history"]]
        dd = drawdown_status(hist, rules)
        if dd["warnung"]:
            alerts.append(f"{p}: Drawdown {dd['drawdown']*100:.1f} % ≥ Warnschwelle 10 %")
        lines.append(f"| {p} | {v:,.2f} € | {(v/forward.START_CAPITAL-1)*100:+.2f} % | {dd['drawdown']*100:.1f} % |")
    lines.append("")

    ok, msg = journal.verify()
    lines += ["## Hinweise", *(f"- ⚠ {a}" for a in alerts), f"- Journal: {msg} ({len(journal.read())} Einträge)", ""]
    lines += ["## Meine mögliche Handlung",
              "Keine. Alle Signale sind virtuell (Forward-Test). Echtgeld-Orders sind nicht autorisiert." if not alerts
              else "Hinweise oben lesen; Echtgeld-Handlungen sind weiterhin nicht autorisiert."]
    _write(lines, now)
    # Benachrichtigungs-Flag: nur bei echten Ereignissen (Signal, Ausführung, Warnung, Datenausfall)
    flag = ROOT / "reports" / "alert.txt"
    reasons = [f"{e['aktion']} {e['asset']} ({e['portfolio']})" for e in sigs] + \
              [f"ausgeführt: {e['aktion']} {e['asset']}" for e in execs] + alerts + \
              [f"Daten fehlen: {k}" for k in failures]
    if reasons:
        flag.write_text("; ".join(reasons)[:250])
    elif flag.exists():
        flag.unlink()
    return 0


def _write(lines: list[str], now: datetime) -> None:
    out = ROOT / "reports"
    (out / "daily").mkdir(parents=True, exist_ok=True)
    txt = "\n".join(lines) + "\n"
    (out / "daily" / f"{now:%Y-%m-%d}.md").write_text(txt)
    (out / "latest.md").write_text(txt)
    print(txt)


if __name__ == "__main__":
    sys.exit(main())
