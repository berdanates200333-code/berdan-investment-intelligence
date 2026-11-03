"""Automatische Erfolgskontrolle: bewertet fällige Prognosen (append-only in bewertungen.jsonl) und rechnet Kennzahlen."""
from __future__ import annotations

from datetime import date, datetime, timezone

import pandas as pd

from .. import journal
from . import jr

ROUNDTRIP_COST_PCT = 0.30      # vorab festgelegte Kostenannahme je Rundreise für "wirtschaftlich sinnvoll" (Gebühren+Spread+Slippage)
GRACE_DAYS = 5                 # Kalendertage nach Fälligkeit, danach "nicht auswertbar" bei fehlenden Daten
REF_TOL = 0.005                # erlaubte Abweichung journalisierter Referenzkurs vs. Datenquelle (0,5 %)


def _decision_ok(entsch: str, ist_pct: float, bewerten: bool):
    if not bewerten:
        return None
    if entsch == "KAUFEN":
        return ist_pct - ROUNDTRIP_COST_PCT > 0
    if entsch == "HALTEN":
        return ist_pct > 0
    return ist_pct <= ROUNDTRIP_COST_PCT      # VERKAUFEN / NICHT KAUFEN: Verzicht war sinnvoll, wenn Gewinn nach Kosten ausblieb


def _critique(erw, ist, p, richtig):
    if richtig and abs(ist - erw) <= max(1.0, abs(erw)):
        return "Richtung und Größenordnung im Rahmen."
    parts = []
    if not richtig:
        parts.append(f"Richtung falsch (erwartet {erw:+.2f} %, tatsächlich {ist:+.2f} %); bei P(positiv)={p:.0%} war das {'ein erwartbarer Fehlschlag' if (p < 0.6) else 'ein deutlicher Fehlschlag'}")
    if abs(ist - erw) > max(1.0, 2 * abs(erw)):
        parts.append(f"Größenfehler {ist - erw:+.2f} Prozentpunkte: Schwankung wurde unterschätzt")
    return "; ".join(parts) + ". Ursprüngliche Annahmen bleiben unverändert dokumentiert."


def evaluate_ki(ki: str, closes_fn, today: date, now: datetime | None = None, base=None) -> list[dict]:
    """closes_fn(yahoo_symbol) -> pd.Series (Index Datum) oder None. Schreibt neue Bewertungen, gibt sie zurück."""
    now = now or datetime.now(timezone.utc)
    pj, bj = (base / "prognosen.jsonl", base / "bewertungen.jsonl") if base else (jr.path(ki), jr.path(ki, "bewertungen.jsonl"))
    done = {(e["prognose_id"], e["horizont"]) for e in journal.read(bj)}
    out = []
    for p in journal.read(pj):
        for h in jr.HORIZONTE:
            hz = p["horizonte"][str(h)]
            if (p["prognose_id"], h) in done or date.fromisoformat(hz["zieltermin"]) > today:
                continue
            s = closes_fn(p["instrument"]["yahoo"])
            base_e = {"typ": "bewertung", "prognose_id": p["prognose_id"], "ki": ki, "horizont": h, "zieltermin_prognose": hz["zieltermin"],
                      "instrument": p["instrument"]["id"], "regelversion": jr.REGELVERSION}
            ref_ts = pd.Timestamp(p["referenz"]["datum"])
            after = s[s.index > ref_ts] if s is not None else None
            if s is None or ref_ts not in s.index or len(after) < h:
                if (today - date.fromisoformat(hz["zieltermin"])).days > GRACE_DAYS:
                    out.append(journal.append({**base_e, "status": "nicht_auswertbar", "grund": "Kursdaten fehlen/unvollständig nach Karenzzeit"}, path=bj, now=now))
                continue
            ref, tgt, tgt_date = float(s.loc[ref_ts]), float(after.iloc[h - 1]), after.index[h - 1]
            ist = (tgt / ref - 1) * 100
            erw, pp = hz["erwartung_pct"], hz["p_positiv"]
            richtig = (erw > 0) == (ist > 0)
            outcome = 1.0 if ist > 0 else 0.0
            ref_dev = abs(p["referenz"]["kurs"] / ref - 1)
            e = {**base_e, "status": "abgeschlossen", "ausgewertet_mit_ziel_datum": str(tgt_date.date()),
                 "referenz_quelle_kurs": round(ref, 4), "ziel_kurs": round(tgt, 4), "ist_pct": round(ist, 3), "prognose_pct": erw,
                 "abweichung_pp": round(ist - erw, 3), "richtung_richtig": richtig, "p_positiv": pp, "positiv_eingetreten": bool(ist > 0),
                 "brier": round((pp - outcome) ** 2, 4), "entscheidung": p["entscheidung"],
                 "entscheidung_sinnvoll": _decision_ok(p["entscheidung"], ist, p.get("entscheidung_bewerten", True)),
                 "datenqualitaet": "ok" if ref_dev <= REF_TOL else f"Referenzkurs weicht {ref_dev*100:.2f} % von Datenquelle ab",
                 "kritik": _critique(erw, ist, pp, richtig)}
            if str(tgt_date.date()) != hz["zieltermin"]:
                e["datenqualitaet"] += f"; Zieltermin laut Datenreihe {tgt_date.date()} statt {hz['zieltermin']} (Kalenderfehler in der Prognose)"
            out.append(journal.append(e, path=bj, now=now))
    return out


def stats(ki: str, today: date, base=None) -> dict:
    pj, bj = (base / "prognosen.jsonl", base / "bewertungen.jsonl") if base else (jr.path(ki), jr.path(ki, "bewertungen.jsonl"))
    progs, bews = journal.read(pj), journal.read(bj)
    res = {"prognosen": len(progs), "horizonte": {}}
    for h in jr.HORIZONTE:
        total = len(progs)
        b = [x for x in bews if x["horizont"] == h]
        ab = [x for x in b if x["status"] == "abgeschlossen"]
        na = len(b) - len(ab)
        r = {"gesamt": total, "abgeschlossen": len(ab), "nicht_auswertbar": na, "offen": total - len(b)}
        if ab:
            dec = [x["entscheidung_sinnvoll"] for x in ab if x["entscheidung_sinnvoll"] is not None]
            r.update(trefferquote=sum(x["richtung_richtig"] for x in ab) / len(ab), mae_pp=sum(abs(x["abweichung_pp"]) for x in ab) / len(ab),
                     bias_pp=sum(x["abweichung_pp"] for x in ab) / len(ab), brier=sum(x["brier"] for x in ab) / len(ab),
                     entscheidung_sinnvoll=(sum(dec) / len(dec)) if dec else None, n_entscheidungen=len(dec))
        res["horizonte"][h] = r
    return res
