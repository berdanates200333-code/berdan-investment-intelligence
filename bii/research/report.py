"""Berichte des Research-Monitors (Markdown) und Benachrichtigungsentscheidung."""
from __future__ import annotations

from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REP = ROOT / "reports" / "research"


def money(v, cur="USD"):
    if v is None:
        return "–"
    a = abs(v)
    if a >= 1e9:
        return f"{v/1e9:,.1f} Mrd. {cur}"
    if a >= 1e6:
        return f"{v/1e6:,.0f} Mio. {cur}"
    return f"{v:,.2f} {cur}"


def pct(v):
    return "–" if v is None else f"{v*100:.1f} %"


def company_md(p: dict, events: list[dict]) -> str:
    f = p.get("finanzen", {})
    t, k, b = f.get("ttm", {}), f.get("kennzahlen", {}), f.get("bilanz", {})
    L = [f"# {p['name']} ({p['ticker']})", f"Stand {p['stand_utc']} · Daten: SEC EDGAR (offiziell), Kurs: Yahoo (inoffiziell)", "",
         f"**SEC-Finanzdaten:** {p.get('sec_daten_status', 'aktuell')}", "",
         "## Geschäftsmodell", p["geschaeftsmodell"]["text"] or "–", f"_Quelle: {p['geschaeftsmodell']['quelle']}_", ""]
    bel = p.get("belege") or {}
    if bel.get("item1_auszug"):
        L += [f"**Auszug 10-K Item 1** ([Quelle]({bel['quelle']})): „{bel['item1_auszug'][:900]} …“", ""]
    L += ["## Kennzahlen (letzte 12 Monate)", "| Kennzahl | Wert | bis |", "|---|---|---|"]
    for name, key in (("Umsatz", "umsatz"), ("Bruttogewinn", "bruttogewinn"), ("Operatives Ergebnis", "operatives_ergebnis"),
                      ("Nettoergebnis", "nettoergebnis"), ("Operativer Cashflow", "operativer_cashflow"),
                      ("Investitionen Sachanlagen", "investitionen_sachanlagen"), ("Aktienvergütung", "aktienverguetung"),
                      ("Aktienrückkäufe", "aktienrueckkaeufe")):
        if key in t:
            L.append(f"| {name} | {money(t[key]['wert'])} | {t[key]['bis']} |")
    L += ["", "| Kennzahl | Wert |", "|---|---|"]
    for name, key, fmt in (("Bruttomarge", "bruttomarge", pct), ("Operative Marge", "operative_marge", pct),
                           ("Nettomarge", "nettomarge", pct), ("F&E-Quote", "fue_quote", pct),
                           ("Free Cashflow", "free_cashflow", money), ("FCF-Marge", "fcf_marge", pct),
                           ("FCF nach Aktienvergütung", "free_cashflow_nach_sbc", money), ("Capex-Quote", "capex_quote", pct),
                           ("Liquidität inkl. kurzfr. Wertpapiere", "liquiditaet", money), ("Finanzschulden", "finanzschulden", money),
                           ("Nettoliquidität", "nettoliquiditaet", money),
                           ("Umsatzwachstum letztes Quartal (ggü. Vorjahr)", "umsatzwachstum_yoy_quartal", pct),
                           ("Umsatzwachstum letztes Geschäftsjahr", "umsatzwachstum_letztes_gj", pct)):
        if key in k:
            L.append(f"| {name} | {fmt(k[key])} |")
    if "aktien_ausstehend" in b:
        L.append(f"| Aktien ausstehend | {b['aktien_ausstehend']['wert']/1e9:,.3f} Mrd. (Stichtag {b['aktien_ausstehend']['stichtag']}) |")
    qs = f.get("quartale", {}).get("umsatz", [])
    if qs:
        L += ["", "**Umsatz je Quartal:** " + " · ".join(f"{q['ende']}: {money(q['wert'])}" + ("*" if q["quelle"].get("abgeleitet") else "") for q in qs[-6:]),
              "_* abgeleitet aus kumulierten Werten (z. B. Q4 = Geschäftsjahr − 9 Monate)_"]
    seg = p.get("segmente") or {}
    if seg.get("achsen"):
        per = seg["periode"]
        L += ["", f"## Segmente ({seg.get('formular')} · {per['von']} bis {per['bis']}, [XBRL-Quelle]({seg.get('quelle')}))"]
        for axis, items in seg["achsen"].items():
            L += [f"**{axis}** (Abdeckung {pct(seg.get('abdeckung', {}).get(axis))} des Gesamtumsatzes)", "| Segment | Umsatz | Anteil | Operatives Ergebnis |", "|---|---|---|---|"]
            for n, v in sorted(items.items(), key=lambda kv: -kv[1].get("umsatz", 0)):
                L.append(f"| {n} | {money(v.get('umsatz'))} | {pct(v.get('anteil'))} | {money(v.get('operatives_ergebnis'))} |")
            L.append("")
    if bel:
        L += ["## Management und Beziehungen (Belegprüfung im 10-K)", f"_Quelle: [{bel.get('accession')}]({bel.get('quelle')}); Textsuche, Ausschnitt prüfen_", "",
              "| Art | Name/Partner | Beleg | Ausschnitt |", "|---|---|---|---|"]
        for m in bel.get("management", []):
            L.append(f"| {m['rolle']} | {m['name']} | {m['beleg']} | {(m['ausschnitt'] or '')[:140]} |")
        for r in bel.get("beziehungen", []):
            L.append(f"| {r['art']} | {r['partner']} | {r['beleg']} ({r['treffer']}×) | {(r['ausschnitt'] or '')[:140]} |")
        L.append("")
    v = p.get("bewertung")
    if v:
        L += ["## Bewertung (Szenarien, Annahmen siehe These)", f"Kurs: {money(p['kurs']['kurs']) if p.get('kurs') else '–'} ({p['kurs']['datum'] if p.get('kurs') else ''}, {p['kurs']['quelle'] if p.get('kurs') else ''})", "",
              "| Szenario | Wert je Aktie | Abstand zum Kurs | Anteil Endwert |", "|---|---|---|---|"]
        for n, s in v["szenarien"].items():
            L.append(f"| {n} | {money(s['wert_je_aktie'])} | {pct(s.get('abstand_zum_kurs'))} | {pct(s['anteil_endwert'])} |")
        if v.get("eingepreistes_wachstum_10j") is not None:
            L.append(f"\n**Eingepreist:** Der aktuelle Börsenwert entspricht etwa **{pct(v['eingepreistes_wachstum_10j'])} Umsatzwachstum pro Jahr über 10 Jahre** "
                     f"bei gleichbleibender heutiger FCF-Marge ({pct(p['finanzen']['kennzahlen'].get('fcf_marge'))}) und {pct(v['annahmen']['diskontsatz'])} Diskontsatz.")
        if v.get("einstieg"):
            e = v["einstieg"]
            L.append(f"\n**Einstiegskriterium:** {e.get('regel', e.get('grund'))} → {'ERFÜLLT' if e['erfuellt'] else 'nicht erfüllt'}"
                     + (f" (Schwelle {money(e['schwelle'])})" if e.get("schwelle") else ""))
        L.append("")
    L += ["## Ereignisse (letzte 30 Tage, ohne Insider-Formulare)", "| Datum | Wichtigkeit | Ereignis | Zuverlässigkeit |", "|---|---|---|---|"]
    for e in sorted(events, key=lambda e: e.get("veroeffentlicht") or "", reverse=True)[:25]:
        L.append(f"| {(e.get('veroeffentlicht') or '')[:10]} | {e['wichtigkeit']} | [{e['titel'][:90]}]({e['quelle']['url']}) | {e['zuverlaessigkeit'][:45]} |")
    return "\n".join(L) + "\n"


def write_all(run, cfg, profiles: dict, newsstats: dict) -> None:
    REP.mkdir(parents=True, exist_ok=True)
    since = (run.now - timedelta(days=30)).isoformat()[:10]
    for c in cfg:
        p = profiles.get(c["ticker"])
        if p:
            ev = [e for e in run.store.events(c["ticker"], since=since) if e.get("formular") not in ("4", "144")]
            (ROOT / "research" / "db" / "companies" / f"{c['ticker']}.md").write_text(company_md(p, ev))
    fresh = [e for e in run.new if e.get("analyse_status") != "bestand"]
    high = [e for e in fresh if e["wichtigkeit"] == "hoch"]
    mid = [e for e in fresh if e["wichtigkeit"] == "mittel"]
    qs = run.ops.get("quellenstatus", {})
    L = [f"# Research-Monitor – {run.now:%d.%m.%Y %H:%M} UTC", "Regelbasierte Erfassung (Python). Analysen durch Claude stehen in `research/analyses/`.",
         f"Quellen: offizielle Newsrooms ✓ · Google News/Yahoo RSS ✓ · SEC EDGAR: {qs.get('sec', 'aktiv')}", "",
         "## Überblick", "| Unternehmen | Kurs | Umsatz TTM | Op. Marge | FCF-Marge | Eingepreistes Wachstum | Neue Ereignisse (hoch/mittel/niedrig) |", "|---|---|---|---|---|---|---|"]
    for c in cfg:
        p = profiles.get(c["ticker"], {})
        k = p.get("finanzen", {}).get("kennzahlen", {})
        t = p.get("finanzen", {}).get("ttm", {})
        ev = [e for e in fresh if e["ticker"] == c["ticker"]]
        cnt = "/".join(str(sum(e["wichtigkeit"] == w for e in ev)) for w in ("hoch", "mittel", "niedrig"))
        L.append(f"| [{c['ticker']}](../../research/db/companies/{c['ticker']}.md) | {money(p['kurs']['kurs']) if p.get('kurs') else '–'} | "
                 f"{money(t.get('umsatz', {}).get('wert'))} | {pct(k.get('operative_marge'))} | {pct(k.get('fcf_marge'))} | "
                 f"{pct((p.get('bewertung') or {}).get('eingepreistes_wachstum_10j'))} | {cnt} |")
    L += ["", "## Neue wichtige Ereignisse"]
    for e in high + mid:
        L.append(f"- **{e['wichtigkeit']}** {e['ticker']} {(e.get('veroeffentlicht') or '')[:10]}: [{e['titel'][:110]}]({e['quelle']['url']}) – {e['zuverlaessigkeit']}; {e['regel']}")
    if not high + mid:
        L.append("- keine")
    L += ["", f"## Zur KI-Analyse vorgemerkt: {len(run.queued)}", *[f"- `{q}`" for q in run.queued]]
    seeded = sum(1 for e in run.new if e.get("analyse_status") == "bestand")
    if seeded:
        L.append(f"\n_{seeded} ältere Einträge wurden beim ersten Lauf als Bestand erfasst (keine Benachrichtigung)._")
    L += ["", "## Nachrichtenabruf (Google News RSS, Yahoo Finance RSS)", *[f"- {t}: {s['abgerufen']} abgerufen, {s['neu']} neu, {s['dubletten']} Dubletten verworfen" for t, s in newsstats.items()]]
    if run.errors:
        L += ["", "## Datenfehler (dieser Lauf)", *[f"- `{k}`: {v} (seit {run.ops['fehler'][k]['folge']} Läufen)" for k, v in run.errors.items()]]
    (REP / "latest.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))
    reasons = [f"{e['ticker']}: {e['titel'][:70]}" for e in high]
    persistent = [k for k, v in run.ops["fehler"].items() if v["folge"] == 2 or (v["folge"] > 2 and (v["folge"] - 2) % 5 == 0)]
    if persistent:
        reasons.append(f"Datenfehler seit ≥2 Läufen: {', '.join(persistent)[:100]}")
    flag, qflag = REP / "alert.txt", REP / "queue.txt"
    flag.write_text("; ".join(reasons)[:240]) if reasons else flag.unlink(missing_ok=True)
    qflag.write_text("\n".join(run.queued)) if run.queued else qflag.unlink(missing_ok=True)
