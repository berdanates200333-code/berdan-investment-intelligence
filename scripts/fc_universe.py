"""Universum live prüfen (Datenstufe A + Liquidität) und Status schreiben."""
import json
import sys
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bii.forecast import live, universe  # noqa: E402

now = datetime.now(timezone.utc)
lv = live.Live(now, "2y")
st = universe.check_universe(lv, now)
st["probleme"] = lv.log
st["abrufe"] = lv.requests
universe.STATUS.write_text(json.dumps(st, indent=1, ensure_ascii=False))
n = sum(v["zugelassen"] for v in st["instrumente"].values())
print(f"zugelassen: {n}/{len(st['instrumente'])}")
for k, v in st["instrumente"].items():
    if not v["zugelassen"]:
        print("nicht zugelassen:", k, v["stufe"], v.get("gruende") or v.get("grund"))

# Referenzdaten für die tägliche Claude-Routine (kein Netzzugriff nötig): nur Stufe-A-Instrumente, letzter abgeschlossener Balken
import numpy as np  # noqa: E402
ref = {"erstellt_utc": now.isoformat(timespec="seconds"), "hinweis": "Schlusskurse sind split-bereinigt, ohne Dividenden; Stufe A = Zweitquelle bestätigt.", "instrumente": {}}
for inst in universe.load()["stufe1_handelbar"] + universe.load()["benchmarks"]:
    q = lv.get(inst)
    if q is None or not st["instrumente"][inst["id"]]["zugelassen"]:
        continue
    d, c = q.df.index[-1], q.df.close
    tr = pd.concat([q.df.high - q.df.low, (q.df.high - c.shift()).abs(), (q.df.low - c.shift()).abs()], axis=1).max(axis=1)
    ref["instrumente"][inst["id"]] = {"name": inst.get("art"), "waehrung": inst["waehrung"], "isin": inst.get("isin"), "klasse": inst.get("klasse"), "venue": inst["venue"], "datum": str(d.date()),
        "schluss": round(float(c.iloc[-1]), 4), "stufe": "A_bestaetigt", "zweitquelle": q.secondary_name, "sma50": round(float(c.tail(50).mean()), 2), "sma200": round(float(c.tail(200).mean()), 2),
        "atr14": round(float(tr.tail(14).mean()), 3), "rendite_5t_pct": round(float((c.iloc[-1] / c.iloc[-6] - 1) * 100), 2), "rendite_20t_pct": round(float((c.iloc[-1] / c.iloc[-21] - 1) * 100), 2),
        "rendite_60t_pct": round(float((c.iloc[-1] / c.iloc[-61] - 1) * 100), 2), "volumen_faktor": round(float(q.df.volume.iloc[-1] / q.df.volume.tail(21).iloc[:-1].mean()), 2),
        "dollarvolumen_20t_mio": st["instrumente"][inst["id"]]["dollarvolumen_20t_mio"]}
try:
    from bii.papertrading.data import ecb_eurusd
    fx = ecb_eurusd()
    ref["eur_usd"] = {"datum": str(fx.index[-1].date()), "usd_je_eur": float(fx.iloc[-1])}
except Exception as e:  # noqa: BLE001
    ref["eur_usd"] = None
(ROOT / "forecast" / "daten").mkdir(exist_ok=True)
(ROOT / "forecast" / "daten" / "referenz.json").write_text(json.dumps(ref, indent=1, ensure_ascii=False))
print("Referenzdaten:", len(ref["instrumente"]))

# Passives Mischportfolio (einfach, vorab festgelegt): 60 % EUNL + 30 % Gold (GLD, USD->EUR) + 10 % Bargeld. Append-only Kurslog je Handelstag.
mixf = ROOT / "forecast" / "daten" / "mix.jsonl"
try:
    e, g, fxr = ref["instrumente"]["EUNL.DE"], ref["instrumente"]["GLD"], ref["eur_usd"]
    last = json.loads(mixf.read_text().splitlines()[-1])["datum"] if mixf.exists() and mixf.read_text().strip() else None
    if fxr and e["datum"] == g["datum"] and (last is None or e["datum"] > last):
        with mixf.open("a") as f:
            f.write(json.dumps({"datum": e["datum"], "eunl_eur": e["schluss"], "gld_usd": g["schluss"], "usd_je_eur": fxr["usd_je_eur"], "fx_datum": fxr["datum"]}) + "\n")
        print("Mix-Log ergänzt:", e["datum"])
except Exception as ex:  # noqa: BLE001
    print("Mix-Log nicht ergänzt:", type(ex).__name__)
