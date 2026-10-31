"""Nachvollziehbarer Research-Bericht (Markdown). Jede Zeile nennt Quelle, Datum und Zuverlässigkeit."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .store import QUEUE, R, ROOT, read_json

BERLIN = ZoneInfo("Europe/Berlin")


def _m(v, unit="", pct=False, d=1):
    if v is None:
        return "–"
    if pct:
        return f"{v * 100:+.{d}f} %" if unit == "±" else f"{v * 100:.{d}f} %"
    if abs(v) >= 1e9:
        return f"{v / 1e9:,.1f} Mrd. {unit}".strip()
    if abs(v) >= 1e6:
        return f"{v / 1e6:,.0f} Mio. {unit}".strip()
    return f"{v:,.2f} {unit}".strip()


def _link(title: str, url: str | None) -> str:
    t = title.replace("|", "/")[:110]
    return f"[{t}]({url})" if url and url.startswith("http") else t


def write_report(run, jobs: list[dict], alerts: list[dict]) -> Path:
    now = datetime.now(BERLIN)
    L = [f"# Research-Desk – Lauf {now:%d.%m.%Y %H:%M} Uhr (Europe/Berlin)", "",
         "Periodische Prüfung offizieller Quellen – **kein Echtzeitmonitoring**. Keine Orders, keine Anlageberatung.", "",
         "**Automatisierungsgrad dieses Berichts:** Datenabruf, Dublettenfilter, Kennzahlen, Bewertungsrechnung, "
         "Wichtigkeit und Thesen-Prüfungen sind **Python-Regeln**. Inhaltliche Einordnungen stehen ausschließlich in "
         "`research/desk/analyses/` und sind dort als **KI-Analyse (Claude)** gekennzeichnet.", ""]

    # Betrieb
    st = run.status
    L += ["## Betrieb", f"- Abrufe: {len(run.log.entries)}, davon fehlgeschlagen: {len(run.log.errors())}",
          f"- Neue Erkenntnisse: {len(run.new)} (davon Erstlauf-Basis: {sum(f['erstlauf_basis'] for f in run.new)}), "
          f"Dubletten verworfen: {len(run.skipped)}",
          f"- Erkenntnis-Datenbank: {st.get('kette')} · Analyseaufträge neu: {len(jobs)}"]
    active = {k: v for k, v in st.get("fehlerzaehler", {}).items() if v.get("folge")}
    if active:
        L += ["", "| Quelle | Ursache | in Folge | gesamt |", "|---|---|---|---|"]
        for k, v in sorted(active.items()):
            src, cause = k.split("|", 1)
            L.append(f"| {src} | {cause} | {v['folge']} | {v['gesamt']} |")
    L.append("")

    # Neue Erkenntnisse
    new = sorted([f for f in run.new if not f["erstlauf_basis"]], key=lambda f: -f["wichtigkeit"]["wert"])
    L += ["## Neue Erkenntnisse (ohne Erstlauf-Basis)"]
    if not new:
        L.append("Keine neuen Erkenntnisse seit dem letzten Lauf.")
    else:
        L += ["| Wichtigkeit | Ticker | Typ | Titel | Quelle (Stufe) | veröffentlicht | Grund |", "|---|---|---|---|---|---|---|"]
        for f in new[:40]:
            q = f["quelle"]
            L.append(f"| {f['wichtigkeit']['wert']:.2f} | {', '.join(f['tickers'])} | {f['typ']} | "
                     f"{_link(f['titel'], q.get('url'))} | {q.get('name')} ({f['zuverlaessigkeit']['stufe']}) | "
                     f"{(f.get('veroeffentlicht') or '–')[:16]} | {'; '.join(f['wichtigkeit']['gruende'])[:90]} |")
    L.append("")
    base = [f for f in run.new if f["erstlauf_basis"]]
    if base:
        L += [f"Erstlauf-Basis: {len(base)} ältere Einträge (letzte 120 Tage) wurden als Ausgangsbasis gespeichert, "
              "ohne Alarm und ohne Analyseauftrag.", ""]

    # Unternehmen
    for c in run.universe:
        t = c["ticker"]
        res = run.results.get(t)
        L += [f"## {c['name']} ({t})"]
        if not res:
            L += ["Keine Finanz- oder Bewertungsdaten in diesem Lauf (siehe Betrieb).", ""]
            continue
        fin, val = res["fin"], res["val"]
        k = fin["kennzahlen"]
        L += [f"Quelle: SEC EDGAR XBRL ([companyfacts]({fin['quelle'].get('url')}), abgerufen {fin['quelle'].get('abgerufen_utc')}), "
              f"Stufe A. Abgeleitete Quartalswerte sind als solche gespeichert.", "",
              "| Quartal bis | Umsatz | Wachstum ggü. Vorjahr | Bruttomarge |", "|---|---|---|---|"]
        growth = {x["ende"]: x["wachstum"] for x in k.get("umsatzwachstum_yoy_hist", [])}
        gm = {x["ende"]: x["marge"] for x in k.get("bruttomarge_hist", [])}
        for q in fin["flow"]["umsatz"][-5:]:
            L.append(f"| {q['ende']} | {_m(q['wert'], 'USD')} | {_m(growth.get(q['ende']), '±', True)} | {_m(gm.get(q['ende']), pct=True)} |")
        L += ["", f"- Letzte 12 Monate: Umsatz {_m(k.get('umsatz_ttm'), 'USD')}, Nettoergebnis {_m(k.get('nettoergebnis_ttm'), 'USD')}, "
              f"freier Cashflow {_m(k.get('fcf_ttm'), 'USD')} (Marge {_m(k.get('fcf_marge_ttm'), pct=True)}), "
              f"Aktienvergütung {_m(k.get('aktienverguetung_ttm'), 'USD')}",
              f"- Liquidität {_m(k.get('liquiditaet'), 'USD')}, Finanzschulden {_m(k.get('finanzschulden'), 'USD')}, "
              f"Nettoliquidität {_m(k.get('nettoliquiditaet'), 'USD')}"]
        px, mu = val["kurs"], val["multiplikatoren"]
        if px.get("kurs"):
            chk = px.get("pruefung", {})
            L.append(f"- Kurs {px['kurs']:.2f} {px.get('waehrung') or ''} am {px['datum']} ({px['quelle']}; Prüfung: {chk.get('stufe')}"
                     f"{', Δ ' + format(chk['abweichung'] * 100, '.2f') + ' %' if 'abweichung' in chk else ''})")
            L.append(f"- Bewertung: Marktwert {_m(mu.get('marktkapitalisierung'), 'USD')}, KGV {_m(mu.get('kgv_ttm'))}, "
                     f"EV/Umsatz {_m(mu.get('ev_umsatz_ttm'))}, FCF-Rendite {_m(mu.get('fcf_rendite_ttm'), pct=True)} "
                     f"(nach Aktienvergütung {_m(mu.get('fcf_rendite_nach_sbc_ttm'), pct=True)})")
            rd = val["reverse_dcf"]["impliziertes_umsatzwachstum_pa_je_fcf_marge"]
            if rd:
                parts = [f"bei FCF-Marge {float(m_) * 100:.0f} %: {('%.1f %%' % (g * 100)) if g is not None else 'n. b.'} p. a."
                         for m_, g in rd.items()]
                L.append("- Reverse-DCF (eingepreistes Umsatzwachstum über 10 Jahre, Diskontsatz 9 %, danach 3 %): " + "; ".join(parts))
        else:
            L.append("- Kein Kurs verfügbar – Bewertung entfällt.")
        th = val.get("these")
        if th:
            L += ["", "**These – Szenarien (Rechnung aus den Annahmen in `research/desk/theses/" + t + ".json`):**", "",
                  "| Szenario | Umsatz-CAGR | FCF-Marge | EV/FCF | Wert je Aktie heute | Rendite p. a. ab Kurs |", "|---|---|---|---|---|---|"]
            for sc in th["szenarien"]:
                e = sc["ergebnis"]
                L.append(f"| {sc['name']} | {sc['umsatz_cagr'] * 100:.0f} % | {sc['fcf_marge'] * 100:.0f} % | {sc['ev_fcf_multiple']:.0f} | "
                         f"{e['wert_je_aktie_heute']:.2f} | {_m(e.get('rendite_pa_ab_kurs'), '±', True)} |")
            for kind, label in (("einstieg", "Einstiegskriterien"), ("widerlegung", "Widerlegungsbedingungen")):
                L.append(f"\n{label}:")
                for x in th[kind]:
                    mark = {True: "✅ erfüllt", False: "– nicht erfüllt", None: "? " + x["status"]}[x.get("erfuellt")]
                    L.append(f"- {mark}: {x['text']}" + (f" (Istwerte {x.get('istwerte')})" if x.get("istwerte") else ""))
        else:
            L.append("- Noch keine These hinterlegt.")
        L.append("")

    # Warteschlange und KI-Analysen
    open_jobs = sorted(p.name for p in QUEUE.glob("*.json") if (read_json(p) or {}).get("status") == "offen") if QUEUE.exists() else []
    L += ["## KI-Analysen", f"- Offene Analyseaufträge in `research/desk/queue/`: {len(open_jobs)}"]
    adir = R / "analyses"
    done = sorted(adir.glob("*.md")) if adir.exists() else []
    L += [f"- Vorhandene KI-Analysen: {len(done)}"] + [f"  - [{p.stem}](../{p.relative_to(R)})" for p in done[-10:]]
    if alerts:
        L += ["", "## Benachrichtigung ausgelöst", *(f"- {a['tickers'][0]}: {a['titel']}" for a in alerts)]
    out = R / "reports"
    (out / "daily").mkdir(parents=True, exist_ok=True)
    txt = "\n".join(L) + "\n"
    (out / "latest.md").write_text(txt)
    (out / "daily" / f"{now:%Y-%m-%d_%H%M}.md").write_text(txt)
    return out / "latest.md"
