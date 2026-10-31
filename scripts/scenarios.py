"""Szenariorechnung (KEINE Prognose): Was bedeuten Renditen, Kosten und Steuern in Euro?

Aufruf: python scripts/scenarios.py  -> research/szenarien.md
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TAX = 0.25 * 1.055          # Abgeltungsteuer + Soli, ohne Kirchensteuer (ANNAHME)
PAUSCHBETRAG = 1000.0       # Sparer-Pauschbetrag Einzelperson (wird von ALLEN Kapitalerträgen geteilt)
CAPITALS = [1_000, 5_000, 10_000, 20_000]
SCENARIOS = {"Crash-Jahr": -0.30, "Schwaches Jahr": -0.10, "Seitwärts": 0.0, "Basis (hist. ~7 %)": 0.07, "Sehr gutes Jahr": 0.20}
TRADES_PER_YEAR = 24        # Orders/Jahr (z. B. 12 Positionswechsel à Kauf + Verkauf)
FEE_PER_ORDER = 1.0         # € je Order (Neobroker-Größenordnung, ANNAHME – beim eigenen Broker prüfen)
SPREAD_SLIPPAGE = 0.001     # 0,1 % je Order auf das gehandelte Volumen
USD_EUR = 0.90              # ANNAHME für Umrechnung, nicht live geprüft
MAX_PLAN_EUR_YEAR = 100 * 12 * USD_EUR  # Claude Max ~100 US$/Monat (zzgl. ggf. USt)


def costs(capital):
    return TRADES_PER_YEAR * (FEE_PER_ORDER + capital * SPREAD_SLIPPAGE)


def net(capital, r):
    gross = capital * r
    c = costs(capital)
    pre_tax = gross - c
    taxable = max(pre_tax - PAUSCHBETRAG, 0.0)
    return gross, c, pre_tax - taxable * TAX


def main():
    md = ["# Szenarien je Kapitalbetrag (Szenario, keine Prognose)", "",
          f"Annahmen: {TRADES_PER_YEAR} Orders/Jahr, {FEE_PER_ORDER:.0f} € je Order, {SPREAD_SLIPPAGE*100:.1f} % Spread/Slippage je Order, "
          f"Steuer {TAX*100:.3f} % nach Sparer-Pauschbetrag {PAUSCHBETRAG:.0f} € (nur wenn dieser nicht anderweitig verbraucht ist), "
          "Verluste werden nur verrechnet, nicht erstattet (hier vereinfacht: keine Steuer im Verlustjahr).", "",
          "## Ergebnis nach einem Jahr in Euro (brutto → Kosten → netto)", "",
          "| Kapital | " + " | ".join(SCENARIOS) + " | Handelskosten/Jahr | Kosten in % |",
          "|---" * (len(SCENARIOS) + 3) + "|"]
    for cap in CAPITALS:
        cells = []
        for r in SCENARIOS.values():
            g, c, n = net(cap, r)
            cells.append(f"{n:+,.0f} €")
        md.append(f"| {cap:,.0f} € | " + " | ".join(cells) + f" | {costs(cap):,.0f} € | {costs(cap)/cap*100:.1f} % |")
    md += ["", "## Welche Rendite wäre nötig, um Fixkosten zu decken?", "",
           "| Kapital | nur Handelskosten | + Claude Max (~1.080 €/J) | + Datenabo 30 €/Monat |", "|---|---|---|---|"]
    for cap in CAPITALS:
        base = costs(cap) / cap
        md.append(f"| {cap:,.0f} € | {base*100:.1f} % | {(base + MAX_PLAN_EUR_YEAR/cap)*100:.1f} % | {(base + 360/cap)*100:.1f} % |")
    md += ["", "## Der eigentlich relevante Wert: Mehrertrag gegenüber dem Welt-ETF", "",
           "Ein Tradingsystem muss nicht absolut, sondern **gegenüber dem passiven ETF** etwas bringen.",
           "", "| Kapital | Mehrrendite +1 % p.a. | +3 % p.a. (sehr optimistisch) | −2 % p.a. (Größenordnung der Minderrendite aktiver Privatanleger, z. B. Barber/Odean) |", "|---|---|---|---|"]
    for cap in CAPITALS:
        md.append(f"| {cap:,.0f} € | {cap*0.01:+,.0f} € | {cap*0.03:+,.0f} € | {cap*-0.02:+,.0f} € |")
    md += ["", "Lesart: Bei 10.000 € bringt selbst eine sehr gute Mehrrendite von 3 % p.a. rund 300 € vor Steuern im Jahr. "
           "Der wirtschaftliche Hebel liegt bei kleinen Beträgen vor allem in niedrigen Kosten, Disziplin und Zeitersparnis – nicht in Tradinggewinnen."]
    out = ROOT / "research" / "szenarien.md"
    out.write_text("\n".join(md) + "\n")
    print(out.read_text())


if __name__ == "__main__":
    main()
