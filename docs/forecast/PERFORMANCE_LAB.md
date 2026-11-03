# Performance Lab (Zusatzauftrag 03.11.2026)

Der Claude-Solo-Test (Hauptkonto, 1 % Risiko, eingefroren) bleibt unverändert. Das Lab ergänzt **getrennte** Konten und Auswertungen auf derselben Engine.

## Bausteine
| Baustein | Datei | Zweck |
|---|---|---|
| Offensivkonto `claude_offensiv` | `bii/forecast/offensiv.py`, `scripts/fc_offensiv.py`, `forecast-offensiv.yml` | 10.000 € virtuell, 2 % Risiko/Trade, ≤ 6 % offenes geplantes Risiko, ≤ 30 % je Instrument, Pause bei −15 % + automatische Risikoanalyse. Handelt die Prognosen des Hauptkontos (reiner **Größeneffekt**) und zusätzlich Prognosen mit `nur_offensiv: true` (**Auswahleffekt**). |
| Risikolabor | `bii/forecast/risikolabor.py`, `forecast-risikolabor.yml` | 1 %/2 %/3 % Risiko bei identischen mechanischen Signalen in 5 Marktphasen (reproduzierbar, rein rechnerisch). Ergebnis: `reports/risikolabor/ergebnis.md`. |
| Auswertung | `bii/forecast/lab.py`, `/cockpit` | Beide Konten nebeneinander, EUNL, passiver Mix (60 % EUNL / 30 % Gold / 10 % Bargeld, Log `forecast/daten/mix.jsonl`), Gewinn je 1 € geplantem Risiko, Stressverlust, Trennung Größen-/Auswahleffekt, Zielmarken (+3/+5/+10 % nach Kosten, experimentell). |

## Fachliche Prüfung der vorgeschlagenen Regeln
- **2 % je Trade:** Mit Stop 2×ATR (≈ 4–6 %) liegt die Position meist bei 35–50 % des Kapitals bevor das 30-%-Limit greift – das Limit begrenzt also die Positionsgröße häufiger als das Risikobudget (Positionen sind dann kleiner, geplantes Risiko < 2 %). Acht Verluste in Folge bei 2 % ergeben −15 % (Pausenschwelle); bei Trefferquoten um 40 % ist eine solche Serie über 60 Tage nicht unwahrscheinlich (P(≥ 6 Verluste in Folge) bei 60 % Verlustquote ≈ 5 % je Startpunkt).
- **6 % offenes Risiko:** entspricht drei voll ausgenutzten Positionen. Die Signale (Ausbruch über 20-Tage-Hoch) sind stark korreliert (Tech-lastiges Universum): drei Positionen sind faktisch eine Wette. Daher meldet das Cockpit einen **Stressverlust** (alle Stops laufen zusätzlich 3 % durch).
- **Stops sind keine Garantie:** Die Engine füllt Kurslücken zum Eröffnungspreis. Das Cockpit weist den schlechtesten Trade als Vielfaches des geplanten Risikos aus; die Risikoanalyse zählt Lücken-Stops. Planrisiko ≠ Maximalverlust. Empfehlung (noch nicht erzwungen): keine Einstiege unmittelbar vor Quartalszahlen – die Claude-Routine prüft Termine und kennzeichnet Ereignisrisiko.
- **30 % je Instrument:** technisch umgesetzt (`max_position_weight`); ETFs mit niedriger ATR können bis zur Grenze gewichtet werden.
- **Pause bei −15 %:** Neue Positionen werden gestoppt (wie beim Hauptkonto manuelle Freigabe nötig), eine Risikoanalyse wird einmalig nach `reports/forecast/risikoanalyse_claude_offensiv_<Datum>.md` geschrieben.
- **Kein Hebel/Leerverkauf/Kredit:** Engine-Regel für beide Konten.

## Trennung der Effekte
1. **Größeneffekt:** gleiche Prognose, gleiche Orderlevel, nur 2 % statt 1 % Risiko → Vergleich des Ergebnisses je Prognose-ID.
2. **Auswahleffekt:** nur-offensiv-Prognosen werden getrennt ausgewiesen und nicht mit (1) vermischt.
3. **Beurteilung:** `lab.verdict` bewertet den Gewinn je 1 € geplantem Risiko; ein höherer Wert spricht für bessere Chancenwahl, ein gleicher oder niedrigerer für reine Risikoausweitung. Unter 5 Trades je Konto gibt es ausdrücklich keine Aussage.

## Grenzen
Kleine Stichprobe (60 Tage); Zielmarken sind kein Versprechen; das Risikolabor nutzt heutige Mega-Caps (Survivorship Bias) und rein mechanische Signale; Steuern sind nicht berücksichtigt; Hebel, Leerverkäufe und Echtgeld sind ausgeschlossen. Die Entscheidung über einen späteren Echtgeld-Piloten bleibt beim Nutzer.
