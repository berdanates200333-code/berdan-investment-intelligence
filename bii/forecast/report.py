"""Berichte für den Chat: übersichtliche Tabellen (Markdown)."""
from __future__ import annotations

from datetime import date

from .. import journal
from . import evaluate, jr, portfolio


def _pct(x, d=1):
    return "–" if x is None else f"{x*100:.{d}f} %"


def stats_table(ki: str, today: date) -> str:
    s = evaluate.stats(ki, today)
    t = "| Horizont | Prognosen | fällig & bewertet | nicht auswertbar | offen | Trefferquote Richtung | Ø Fehler (PP) | Bias (PP) | Brier | Entscheidung sinnvoll |\n|---|---|---|---|---|---|---|---|---|---|\n"
    for h, r in s["horizonte"].items():
        t += (f"| {h} Tag(e) | {r['gesamt']} | {r['abgeschlossen']} | {r['nicht_auswertbar']} | {r['offen']} | {_pct(r.get('trefferquote'),0)} | "
              f"{'–' if 'mae_pp' not in r else format(r['mae_pp'],'.2f')} | {'–' if 'bias_pp' not in r else format(r['bias_pp'],'+.2f')} | "
              f"{'–' if 'brier' not in r else format(r['brier'],'.3f')} | {_pct(r.get('entscheidung_sinnvoll'),0)} |\n")
    return t


def forecasts_table(ki: str, only_date: str | None = None) -> str:
    t = "| ID | Instrument | Referenz | Entscheidung | 1 T: % / Ziel / P | 5 T: % / Ziel / P | 20 T: % / Ziel / P | Belastbarkeit |\n|---|---|---|---|---|---|---|---|\n"
    for p in journal.read(jr.path(ki)):
        if only_date and not p["erstellt_utc"].startswith(only_date):
            continue
        h = p["horizonte"]
        cell = lambda k: f"{h[k]['erwartung_pct']:+.2f} % / {h[k]['zielkurs']:,.2f} / {h[k]['p_positiv']:.0%}"  # noqa: E731
        t += f"| {p['prognose_id']} | {p['instrument']['name']} ({p['instrument']['id']}) | {p['referenz']['kurs']:,.2f} ({p['referenz']['datum']}) | {p['entscheidung']} | {cell('1')} | {cell('5')} | {cell('20')} | {p['belastbarkeit']} |\n"
    return t


def evaluations_table(ki: str, since: str | None = None) -> str:
    t = "| Prognose | Horizont | Prognose % | Ist % | Abw. PP | Richtung | P(+) | Brier | Entscheidung | Status |\n|---|---|---|---|---|---|---|---|---|---|\n"
    for e in journal.read(jr.path(ki, "bewertungen.jsonl")):
        if since and e["erstellt_utc"] < since:
            continue
        if e["status"] != "abgeschlossen":
            t += f"| {e['prognose_id']} | {e['horizont']} T | – | – | – | – | – | – | – | {e['status']}: {e.get('grund','')} |\n"
        else:
            t += (f"| {e['prognose_id']} | {e['horizont']} T | {e['prognose_pct']:+.2f} | {e['ist_pct']:+.2f} | {e['abweichung_pp']:+.2f} | {'✔' if e['richtung_richtig'] else '✘'} | "
                  f"{e['p_positiv']:.0%} | {e['brier']:.3f} | {'–' if e['entscheidung_sinnvoll'] is None else ('sinnvoll' if e['entscheidung_sinnvoll'] else 'nicht sinnvoll')} | {e['datenqualitaet']} |\n")
    return t
