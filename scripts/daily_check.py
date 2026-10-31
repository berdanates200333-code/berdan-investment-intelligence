"""Täglicher Marktcheck: Daten holen, prüfen, Forward-Test fortschreiben, Kurzbericht schreiben.

Aufruf:  python scripts/daily_check.py
Ausgabe: reports/latest.md, reports/daily/JJJJ-MM-TT.md, freitags reports/weekly/JJJJ-Www.md,
         journal/journal.jsonl (append-only), journal/ops_status.json,
         reports/alert.txt (nur wenn eine Benachrichtigung nötig ist; wird nicht versioniert)

Benachrichtigungsregeln (bewusst selten):
  1. neues FT1-Signal KAUF/VERKAUF oder virtuelle Ausführung
  2. Drawdown-Warnschwelle (10 %) NEU überschritten
  3. extreme Tagesbewegung (ETF/Gold ≥ 4 %, Krypto ≥ 12 %), einmal je Kurstag
  4. Datenproblem (Ausfall, blockierte Order, aufgeschobenes Signal) im 2. Lauf in Folge, danach jeden 5. Lauf
  5. freitags: Wochenbericht (dient zugleich als Lebenszeichen des Systems)
Technische Fehler (Absturz, Tests, Journal) meldet der Workflow selbst.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bii import forward, journal  # noqa: E402
from bii.live_data import UNIVERSE, fetch  # noqa: E402
from bii.risk import RiskRules, drawdown_status  # noqa: E402

BERLIN = ZoneInfo("Europe/Berlin")
MOVE_ALERT = {"equity_etf": 0.04, "gold_etc": 0.04, "crypto": 0.12}
OPS = ROOT / "journal" / "ops_status.json"
KIND = {"unabhaengig": "✓", "proxy": "~ Proxy", "handelsplatz": "≈"}
# Ursachen, die die Nutzung der Kurse beeinträchtigen (→ Benachrichtigungsregel 4)
PROBLEM_CAUSES = {"abruf_fehlgeschlagen", "zweitquelle_fehlt", "abweichung_zweitquelle", "veraltet",
                  "unplausibler_sprung", "order_blockiert", "signal_aufgeschoben", "bewertung_letzter_kurs"}
INFO_CAUSES = {"nur_proxy_plausibilisiert"}   # Hinweis, kein Fehler


def load_ops() -> dict:
    return json.loads(OPS.read_text()) if OPS.exists() else {
        "datenproblem_folge": 0, "dd_warnung_aktiv": {}, "bewegung_gemeldet": {}, "letzter_wochenbericht": None}


def update_counters(ops: dict, observed: list[tuple], now_utc) -> dict:
    """ops['datenprobleme']['INSTRUMENT|ursache'] = {folge, gesamt, seit, zuletzt, quellen}.
    Nicht mehr beobachtete Ursachen werden auf folge=0 gesetzt. Rückgabe: aktive Zähler {key: folge}."""
    dp = ops.setdefault("datenprobleme", {})
    seen = {}
    for inst, cause, src in observed:
        seen.setdefault(f"{inst}|{cause}", set()).add(src or "-")
    stamp = now_utc.isoformat(timespec="seconds")
    for k, srcs in seen.items():
        e = dp.setdefault(k, {"folge": 0, "gesamt": 0, "seit": stamp})
        if e["folge"] == 0:
            e["seit"] = stamp
        e["folge"] += 1
        e["gesamt"] += 1
        e["zuletzt"] = stamp
        e["quellen"] = sorted(srcs)
    for k, e in dp.items():
        if k not in seen:
            e["folge"] = 0
    return {k: dp[k]["folge"] for k in seen}


def stale_pending_orders(state: dict, now_utc) -> list[dict]:
    """Prüfung (keine Regeländerung): offene Orders, deren Monatssignal älter ist als der letzte abgeschlossene Monat.
    Nach Regelwerk v1.1 werden sie trotzdem ausgeführt; der Bericht weist darauf hin."""
    last = str(forward.last_completed_month(now_utc))
    out = []
    for o in state.get("pending", []):
        m = o["signal_id"].rsplit("-", 2)
        month = f"{m[-2]}-{m[-1]}" if len(m) == 3 and m[-2].isdigit() else None
        if month and month < last:
            out.append({"key": o["signal_id"],
                        "text": f"Offene Order {o['portfolio']} {o['aktion']} {o['asset']} beruht auf Monatssignal {month}; "
                                f"seitdem ist {last} abgeschlossen (Ausführung nach v1.1 dennoch vorgesehen)"})
    return out


def dq_text(ps) -> str:
    cc = ps.cross_check
    if cc.get("ok") and cc.get("art") == "proxy":
        return f"~ {cc['quelle']}: Verhältnis Δ {cc['abweichung']*100:.2f} % (plausibilisiert, kein Zweitkurs)"
    if cc.get("ok"):
        return f"{KIND.get(cc.get('art'), '✓')} {cc['quelle']}: Δ {cc['abweichung']*100:.2f} %"
    if cc:
        return f"⚠ {cc.get('grund')}"
    return f"⚠ nur {ps.source}, Zweitquelle ausgefallen"


def main(now_utc: pd.Timestamp | None = None) -> int:
    now_utc = now_utc or pd.Timestamp.now(tz="UTC")
    now = now_utc.tz_convert(BERLIN).to_pydatetime()
    ops = load_ops()
    series, failures = {}, {}
    for inst in UNIVERSE:
        try:
            series[inst.key] = fetch(inst)
        except Exception as e:  # noqa: BLE001
            failures[inst.key] = str(e)[:300]

    lines = [f"# Claude Market Briefing – {now:%d.%m.%Y}",
             f"Erstellt {now:%d.%m.%Y %H:%M} Uhr (Europe/Berlin) · Regelwerk FT1 v{forward.RULE_VERSION} · "
             "Tagesschlusskurse, **keine Echtzeitdaten**.", ""]
    reasons: list[str] = []

    result = forward.step(series, now_utc) if series else {
        "events": [], "valuation": {}, "state": forward.load_state(), "blocked": [], "deferred": [], "stale_positions": []}

    # Marktlage
    lines += ["## Gesamtlage", "| Instrument | Letzter Schluss | Datum | 1 Tag | 1 Monat | Trend Monatsende (12M-SMA) | Datenqualität |",
              "|---|---|---|---|---|---|---|"]
    month = forward.last_completed_month(now_utc)
    for key, ps in series.items():
        c = ps.complete(now_utc)
        if len(c) < 30:
            lines.append(f"| {ps.instrument.name[:34]} | – | – | – | – | – | ⚠ zu wenige abgeschlossene Kurse |")
            continue
        d1 = c.iloc[-1] / c.iloc[-2] - 1
        m1 = c.iloc[-1] / c[c.index <= c.index[-1] - pd.Timedelta(days=30)].iloc[-1] - 1
        sig = forward.trend_signal(c, month)
        trend = "–" if sig is None else ("über SMA" if sig["investiert"] else "UNTER SMA") + f" ({sig['abstand_zur_sma']*100:+.1f} %, {sig['monat']})"
        lines.append(f"| {ps.instrument.name[:34]} | {c.iloc[-1]:,.2f} {ps.instrument.currency} | {c.index[-1]:%d.%m.} | "
                     f"{d1*100:+.1f} % | {m1*100:+.1f} % | {trend} | {dq_text(ps)} |")
        bar = str(c.index[-1].date())
        if abs(d1) >= MOVE_ALERT[ps.instrument.asset_class] and ops["bewegung_gemeldet"].get(key) != bar:
            reasons.append(f"{key} Tagesbewegung {d1*100:+.1f} %")
            ops["bewegung_gemeldet"][key] = bar
    for k in failures:
        lines.append(f"| {k} | – | – | – | – | – | ✗ nicht abrufbar |")
    lines += ["", "Datenqualität: ✓ bestätigt durch unabhängigen Zweitkurs · ≈ gleicher Anbieter, anderer Handelsplatz "
              "(eingeschränkt unabhängig) · ~ Proxy plausibilisiert (nur Verhältnisprüfung gegen ein anderes Instrument, "
              "**kein Zweitkurs**; nach Regelwerk v1.1 für Ausführungen zulässig) · ⚠ ungeprüft (keine Orders auf ungeprüfter Basis)", ""]

    # Signale
    sigs = [e for e in result["events"] if e["typ"] == "signal" and e["aktion"] != "HALTEN"]
    holds = [e for e in result["events"] if e["typ"] == "signal" and e["aktion"] == "HALTEN"]
    execs = [e for e in result["events"] if e["typ"] == "ausfuehrung"]
    lines.append("## Signale (FT1, virtuell)")
    if not sigs and not execs:
        lines.append("Keine neuen Signale. **Keine Handlung erforderlich.**")
    for e in sigs:
        d = e["daten"]
        why = ("Startkauf Buy & Hold (Vergleichsportfolio)" if e["portfolio"] == "BENCH" else
               f"Monatsschluss {d.get('monat')} {d.get('monatsschluss')} vs. 12M-SMA {d.get('sma12')}")
        lines.append(f"- **{e['aktion']} {e['asset']}** ({e['portfolio']}), `{e['signal_id']}`: {why}. "
                     f"Zielgewicht {e['zielgewicht']*100:.0f} %. Ausführung zum nächsten geprüften Tagesschluss.")
        reasons.append(f"{e['aktion']} {e['asset']} ({e['portfolio']})")
    for e in holds:
        lines.append(f"- Monatsprüfung {e['daten'].get('monat')}: {e['asset']} ({e['portfolio']}) unverändert – HALTEN.")
    for e in execs:
        lines.append(f"- Ausgeführt (virtuell): {e['aktion']} {e['asset']} ({e['portfolio']}) zu {e['kurs']} am {e['kursdatum']} "
                     f"(geprüft gegen {e['pruefung'].get('quelle')}, Δ {e['pruefung'].get('abweichung', 0)*100:.2f} %).")
        reasons.append(f"ausgeführt {e['aktion']} {e['asset']} ({e['portfolio']})")
    pend = result["state"]["pending"]
    if pend:
        lines.append(f"- Offene virtuelle Orders: {', '.join(o['portfolio'] + ' ' + o['aktion'] + ' ' + o['asset'] for o in pend)}")
    lines.append("")

    # Datenprobleme
    problems = [f"Daten fehlen: {k}" for k in failures]
    problems += [f"Order blockiert {o['portfolio']} {o['asset']}: {o.get('blockiert_grund')}" for o in result["blocked"]]
    problems += [f"Signal aufgeschoben {d['portfolio']} {d['asset']} {d['monat']}: {d['grund']}" for d in result["deferred"]]
    problems += [f"Bewertung mit letztem bekannten Kurs: {a}" for a in result["stale_positions"]]
    # Zähler je Instrument und Ursache (statt eines gemeinsamen Zählers)
    observed = [(k, "abruf_fehlgeschlagen", None) for k in failures]
    observed += [(o["asset"], "order_blockiert", None) for o in result["blocked"]]
    observed += [(d["asset"], "signal_aufgeschoben", None) for d in result["deferred"]]
    observed += [(a, "bewertung_letzter_kurs", None) for a in result["stale_positions"]]
    for key, ps in series.items():
        observed += [(key, i["ursache"], i.get("quelle")) for i in ps.issues]
    for k, n in update_counters(ops, observed, now_utc).items():
        inst, cause = k.split("|", 1)
        if cause in PROBLEM_CAUSES and (n == 2 or (n > 2 and (n - 2) % 5 == 0)):
            reasons.append(f"Datenproblem {inst}/{cause} seit {n} Läufen")
    # Gesamtzähler bleibt zur Kontinuität erhalten (früheres Feld)
    ops["datenproblem_folge"] = ops.get("datenproblem_folge", 0) + 1 if problems else 0
    stale_orders = stale_pending_orders(result["state"], now_utc)
    for so in stale_orders:
        problems.append(so["text"])
        if so["key"] not in ops.setdefault("veraltete_order_gemeldet", []):
            reasons.append(so["text"][:100])
            ops["veraltete_order_gemeldet"].append(so["key"])

    # Portfolio
    rules = RiskRules()
    lines += ["## Virtuelle Portfolios (Start je 10.000 €)", "| Portfolio | Wert | Rendite | Drawdown vom Hoch |", "|---|---|---|---|"]
    for p, v in result["valuation"].items():
        hist = [h["wert"] for h in result["state"]["portfolios"][p]["history"]]
        dd = drawdown_status(hist, rules)
        was = ops["dd_warnung_aktiv"].get(p, False)
        if dd["warnung"] and not was:
            reasons.append(f"{p} Drawdown {dd['drawdown']*100:.1f} % (Warnschwelle 10 %)")
        ops["dd_warnung_aktiv"][p] = bool(dd["warnung"])
        lines.append(f"| {p} | {v:,.2f} € | {(v/forward.START_CAPITAL-1)*100:+.2f} % | {dd['drawdown']*100:.1f} % |")
    lines.append("")

    ok, msg = journal.verify()
    lines += ["## Hinweise", *(f"- ⚠ {p}" for p in problems), f"- Journal: {msg} ({len(journal.read())} Einträge)", ""]
    lines += ["## Meine mögliche Handlung",
              "Keine. Alle Signale sind virtuell (Forward-Test). Echtgeld-Orders sind ausgeschlossen."]

    # Wochenbericht freitags (einmal je Kalenderwoche)
    week = f"{now:%G-W%V}"
    if now.weekday() == 4 and ops.get("letzter_wochenbericht") != week:
        write_weekly(result, now, week, problems)
        ops["letzter_wochenbericht"] = week
        reasons.append(f"Wochenbericht {week}")
        lines += ["", f"Wochenbericht: reports/weekly/{week}.md"]

    _write(lines, now)
    ops["letzter_lauf_utc"] = now_utc.isoformat(timespec="seconds")
    OPS.write_text(json.dumps(ops, indent=2, ensure_ascii=False))
    flag = ROOT / "reports" / "alert.txt"
    if reasons:
        flag.write_text("; ".join(reasons)[:240])
    elif flag.exists():
        flag.unlink()
    return 0 if ok else 1


def write_weekly(result: dict, now: datetime, week: str, problems: list[str]) -> None:
    since = (now - timedelta(days=7)).astimezone(ZoneInfo("UTC")).isoformat()
    week_entries = [e for e in journal.read() if e["erstellt_utc"] >= since[:19]]
    lines = [f"# Wochenbericht {week}", f"Stand {now:%d.%m.%Y %H:%M} Uhr · Regelwerk FT1 v{forward.RULE_VERSION}", "",
             "## Wertentwicklung (virtuell, je 10.000 € Start)", "| Portfolio | Wert | seit Start | 7 Tage | max. Drawdown |", "|---|---|---|---|---|"]
    for p, pf in result["state"]["portfolios"].items():
        hist = pf["history"]
        v = result["valuation"].get(p, hist[-1]["wert"] if hist else forward.START_CAPITAL)
        old = [h for h in hist if h["datum"] <= (now - timedelta(days=7)).strftime("%Y-%m-%d")]
        ref = old[-1]["wert"] if old else forward.START_CAPITAL
        vals = [h["wert"] for h in hist] or [v]
        peak, mdd = vals[0], 0.0
        for x in vals:
            peak = max(peak, x); mdd = min(mdd, x / peak - 1)
        lines.append(f"| {p} | {v:,.2f} € | {(v/forward.START_CAPITAL-1)*100:+.2f} % | {(v/ref-1)*100:+.2f} % | {mdd*100:.1f} % |")
    b, t = result["valuation"].get("BENCH"), result["valuation"].get("TREND")
    if b and t:
        lines += ["", f"TREND gegenüber BENCH: {t - b:+,.2f} € ({(t/b-1)*100:+.2f} %)."]
    lines += ["", "## Journal-Einträge dieser Woche"]
    lines += [f"- {e['erstellt_utc'][:10]} {e['typ']} {e.get('signal_id')} {e.get('aktion', '')}" for e in week_entries] or ["- keine"]
    lines += ["", "## Offene Datenprobleme", *(f"- {p}" for p in problems)] if problems else ["", "## Offene Datenprobleme", "- keine"]
    lines += ["", "Hinweis: Wenige Wochen sind statistisch nicht aussagekräftig. Echtgeld-Handel ist ausgeschlossen."]
    out = ROOT / "reports" / "weekly"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{week}.md").write_text("\n".join(lines) + "\n")


def _write(lines: list[str], now: datetime) -> None:
    out = ROOT / "reports"
    (out / "daily").mkdir(parents=True, exist_ok=True)
    txt = "\n".join(lines) + "\n"
    (out / "daily" / f"{now:%Y-%m-%d}.md").write_text(txt)
    (out / "latest.md").write_text(txt)
    print(txt)


if __name__ == "__main__":
    sys.exit(main())
