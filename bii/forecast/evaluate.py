"""Automatische Erfolgskontrolle (nur Prognosegüte, getrennt von der Tradingperformance).

- Bewertet mit unveränderten Originalwerten aus dem Journal (nie neu gerechnet/umgeschrieben).
- Datenqualität ist ein HARTES Tor: unter der Mindeststufe (Wettbewerb: A, Pilot: B) wird nicht bewertet; nach Karenzzeit
  wird 'nicht_auswertbar' mit Gründen vermerkt (zählt nicht in Trefferquote/Fehler, wird separat ausgewiesen).
- Vergleichsmodelle: Nullveränderung (0 %) und historische Basisrate (nur Daten VOR dem Referenzdatum).
"""
from __future__ import annotations

from datetime import date, datetime, timezone

import numpy as np
import pandas as pd

from .. import journal
from . import calendars, jr, quality

ROUNDTRIP_COST_PCT = 0.30
GRACE_DAYS = 5
REF_TOL = 0.005
MIN_BASE_OBS = 250


def _decision_ok(entsch, ist_pct, bewerten):
    if not bewerten:
        return None
    if entsch == "KAUFEN":
        return ist_pct - ROUNDTRIP_COST_PCT > 0
    if entsch == "HALTEN":
        return ist_pct > 0
    return ist_pct <= ROUNDTRIP_COST_PCT


def baseline(close: pd.Series, ref_ts, h: int) -> dict:
    """Historische Basisrate/-erwartung der h-Tages-Rendite mit Daten bis einschließlich Referenzdatum (kein Look-ahead)."""
    hist = close.loc[:ref_ts]
    r = (hist.shift(-h) / hist - 1).dropna() * 100       # h-Tages-Renditen, deren Ende <= Referenzdatum liegt
    if len(r) < MIN_BASE_OBS:
        return {"basis_beobachtungen": int(len(r))}
    return {"basis_beobachtungen": int(len(r)), "basis_p_positiv": round(float((r > 0).mean()), 4), "basis_erwartung_pct": round(float(r.mean()), 3)}


def _critique(erw, ist, p, richtig):
    if richtig and abs(ist - erw) <= max(1.0, abs(erw)):
        return "Richtung und Größenordnung im Rahmen."
    parts = []
    if not richtig:
        parts.append(f"Richtung falsch (erwartet {erw:+.2f} %, tatsächlich {ist:+.2f} %); bei P(positiv)={p:.0%} war das {'ein erwartbarer Fehlschlag' if p < 0.6 else 'ein deutlicher Fehlschlag'}")
    if abs(ist - erw) > max(1.0, 2 * abs(erw)):
        parts.append(f"Größenfehler {ist - erw:+.2f} Prozentpunkte: Schwankung wurde unterschätzt")
    return "; ".join(parts) + ". Ursprüngliche Annahmen bleiben unverändert dokumentiert."


def evaluate_ki(ki: str, data_fn, today: date, now: datetime | None = None, base=None, phase_override: str | None = None) -> list[dict]:
    """data_fn(instrument_dict) -> quality.QualData | None. Schreibt neue Bewertungen (append-only) und gibt sie zurück."""
    now = now or datetime.now(timezone.utc)
    pj, bj = (base / "prognosen.jsonl", base / "bewertungen.jsonl") if base else (jr.path(ki), jr.path(ki, "bewertungen.jsonl"))
    done = {(e["prognose_id"], e["horizont"]) for e in journal.read(bj)}
    out = []
    for p in journal.read(pj):
        phase = phase_override or p.get("phase", "pilot")
        for h in jr.HORIZONTE:
            hz = p["horizonte"][str(h)]
            if (p["prognose_id"], h) in done or date.fromisoformat(hz["zieltermin"]) > today:
                continue
            base_e = {"typ": "bewertung", "prognose_id": p["prognose_id"], "ki": ki, "horizont": h, "zieltermin_prognose": hz["zieltermin"],
                      "instrument": p["instrument"]["id"], "phase": phase, "regelversion": jr.REGELVERSION}
            overdue = (today - date.fromisoformat(hz["zieltermin"])).days > GRACE_DAYS
            qd = data_fn(p["instrument"])
            ref_ts = pd.Timestamp(p["referenz"]["datum"])
            venue = calendars.venue_of(p["instrument"])
            reason = None
            if qd is None:
                reason = "keine Kursdaten"
            else:
                after = qd.df[qd.df.index > ref_ts]
                if ref_ts not in qd.df.index or len(after) < h:
                    reason = "Referenz- oder Zielbalken fehlt"
                else:
                    tgt_date = after.index[h - 1]
                    ok_r, tr = qd.allowed(ref_ts, phase)
                    ok_t, tt = qd.allowed(tgt_date, phase)
                    if not (ok_r and ok_t):
                        reason = f"Datenqualität unzureichend (Referenz {tr}, Ziel {tt}, Mindestens {quality.MIN_TIER[phase]}): {'; '.join(qd.reasons) or 'ohne Zweitquellen-Bestätigung'}"
            if reason:
                if overdue:
                    out.append(journal.append({**base_e, "status": "nicht_auswertbar", "grund": reason}, path=bj, now=now))
                continue
            ref, tgt = float(qd.df.loc[ref_ts, "close"]), float(after.iloc[h - 1]["close"])
            ist = (tgt / ref - 1) * 100
            erw, pp = hz["erwartung_pct"], hz["p_positiv"]
            richtig = (erw > 0) == (ist > 0)
            outcome = 1.0 if ist > 0 else 0.0
            ref_dev = abs(p["referenz"]["kurs"] / ref - 1)
            bl = baseline(qd.df["close"], ref_ts, h)
            if "basis_p_positiv" in bl:
                bl["basis_brier"] = round((bl["basis_p_positiv"] - outcome) ** 2, 4)
                bl["basis_abs_fehler_pp"] = round(abs(ist - bl["basis_erwartung_pct"]), 3)
            bl["null_abs_fehler_pp"] = round(abs(ist), 3)
            bl["konstant_0_5_brier"] = round((0.5 - outcome) ** 2, 4)
            e = {**base_e, "status": "abgeschlossen", "ausgewertet_mit_ziel_datum": str(tgt_date.date()), "datenstufe_referenz": tr, "datenstufe_ziel": tt,
                 "zweitquelle": qd.secondary_name, "referenz_quelle_kurs": round(ref, 4), "ziel_kurs": round(tgt, 4), "ist_pct": round(ist, 3),
                 "prognose_pct": erw, "abweichung_pp": round(ist - erw, 3), "richtung_richtig": richtig, "p_positiv": pp, "positiv_eingetreten": bool(ist > 0),
                 "brier": round((pp - outcome) ** 2, 4), "entscheidung": p["entscheidung"],
                 "entscheidung_sinnvoll": _decision_ok(p["entscheidung"], ist, p.get("entscheidung_bewerten", True)),
                 "referenz_abweichung_journal_pct": round(ref_dev * 100, 3), "vergleich": bl,
                 "datenhinweis": None if ref_dev <= REF_TOL else f"Journal-Referenz weicht {ref_dev*100:.2f} % von der Datenquelle ab (Auswertung nutzt Datenreihe, Journalwerte bleiben unverändert)",
                 "kapitalmassnahmen_im_zeitraum": bool(qd.actions.get("splits")),
                 "kritik": _critique(erw, ist, pp, richtig)}
            out.append(journal.append(e, path=bj, now=now))
    return out


def stats(ki: str, today: date, base=None, phase: str | None = None) -> dict:
    pj, bj = (base / "prognosen.jsonl", base / "bewertungen.jsonl") if base else (jr.path(ki), jr.path(ki, "bewertungen.jsonl"))
    progs = [p for p in journal.read(pj) if phase is None or p.get("phase", "pilot") == phase]
    ids = {p["prognose_id"] for p in progs}
    bews = [b for b in journal.read(bj) if b["prognose_id"] in ids]
    res = {"phase": phase or "alle", "prognosen": len(progs), "horizonte": {}}
    for h in jr.HORIZONTE:
        b = [x for x in bews if x["horizont"] == h]
        ab = [x for x in b if x["status"] == "abgeschlossen"]
        r = {"gesamt": len(progs), "abgeschlossen": len(ab), "nicht_auswertbar": len(b) - len(ab), "offen": len(progs) - len(b)}
        if ab:
            dec = [x["entscheidung_sinnvoll"] for x in ab if x["entscheidung_sinnvoll"] is not None]
            r.update(trefferquote=float(np.mean([x["richtung_richtig"] for x in ab])), mae_pp=float(np.mean([abs(x["abweichung_pp"]) for x in ab])),
                     bias_pp=float(np.mean([x["abweichung_pp"] for x in ab])), brier=float(np.mean([x["brier"] for x in ab])),
                     null_mae_pp=float(np.mean([x["vergleich"]["null_abs_fehler_pp"] for x in ab])),
                     entscheidung_sinnvoll=float(np.mean(dec)) if dec else None, n_entscheidungen=len(dec))
            bb = [x for x in ab if "basis_brier" in x["vergleich"]]
            if bb:
                r.update(basis_brier=float(np.mean([x["vergleich"]["basis_brier"] for x in bb])), brier_vergleichbar=float(np.mean([x["brier"] for x in bb])), n_basis=len(bb))
        res["horizonte"][h] = r
    days = {p["erstellt_utc"][:10] for p in progs}
    res["prognosetage"] = len(days)
    return res
