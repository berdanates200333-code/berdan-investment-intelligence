# Strategie Paper-Trading v1.0 – Swing-Trading (Long only, rein virtuell)

**Status: eingefroren ab 02.11.2026.** Maßgeblich ist der Code `bii/papertrading/rules_v1_0.py` (SHA-256 in `tests/test_papertrading.py` und `papertrading/registry.json` festgeschrieben). Änderungen nur als neue Version (`rules_v1_1.py`, eigener Ordner `papertrading/v1.1/`, eigener Teststart); v1.0-Ergebnisse, Journal und Entscheidungen bleiben unverändert.
Testzeitraum: 02.11.2026 – 24.01.2027 (12 Wochen), Abschlussbewertung ab 25.01.2027. Keine Echtgeld-Orders, keine Broker-Verbindung, keine kostenpflichtigen Dienste. FT1 (Journal, Regelwerk, Strategietests) bleibt unverändert; das Paper-Trading schreibt nur nach `papertrading/` und `reports/papertrading/`.

## Konten
- **Aktiv:** 10.000 € virtuell, Konto in EUR, Handel in USD (US-Aktien), Umrechnung mit EZB-Referenzkurs des Vortags.
- **Benchmark (unabhängig):** 10.000 € in iShares Core MSCI World (EUNL.DE), Kauf zur Eröffnung am ersten Testtag mit denselben Kostenannahmen, danach Buy-and-hold.

## Universum
30 liquide US-Standardwerte (Liste in der Regeldatei, vor Teststart von Hand festgelegt; mögliche Auswahlverzerrung, siehe Grenzen). Marktfilter und Referenz für relative Stärke: SPY (wird nicht gehandelt).

## Einstiegsregeln (alle müssen am Tagesschluss d erfüllt sein; nur Daten bis d)
1. Marktfilter: SPY-Schluss > SMA100.
2. Trend: Schluss > SMA50 > SMA200.
3. Ausbruch: Schluss über dem höchsten Hoch der 20 Vortage.
4. Volumen ≥ 1,2 × Ø 20 Tage; RSI14 zwischen 50 und 78; ATR14 zwischen 1 % und 6 % des Kurses; Ø Dollarvolumen 20 Tage ≥ 100 Mio. $.
5. Relative Stärke 60 Tage größer als bei SPY. Ereignistag (|Tagesbewegung| > 8 %) → kein Einstieg.
6. Rangfolge: relative Stärke + Volumenfaktor; höchstens 2 neue Positionen je Tag, höchstens 5 gleichzeitig, nie dasselbe Wertpapier doppelt.
7. **Vetos (vor der Orderplanung):** (a) Datenprüfung: Stooq-Schlusskurs weicht > 2 % ab → Verzicht; (b) Nachrichten-Check (Google News RSS, 3 Tage): Negativ-Schlagwort wie *probe, investigation, lawsuit, fraud, downgrade, recall …* → Verzicht; (c) Claude-Veto aus `papertrading/review/vetos.jsonl` (append-only, mit Begründung und Quellen).
   Nicht erreichbare Zweitquelle/Nachrichten blockieren nicht, werden aber als „ungeprüft“ im Orderplan dokumentiert.

## Order, Ausstieg, Größe
- Kauf als **Limit-Order** für den nächsten Handelstag: Limit = Schluss + 1 %. Eröffnet der Kurs darüber oder bereits unter dem Stop → **nicht ausgeführt** (dokumentiert).
- Stop = Einstieg − 2 × ATR14 (Stop-Market, bei Kurslücke Ausführung zur Eröffnung); Kursziel = 2,5 R; nach +1 R Stop auf Einstand; Zeitstopp nach 20 Handelstagen (Verkauf zur Eröffnung). Stop vor Ziel, wenn beides am selben Tag erreicht wird (konservativ).
- **Positionsgröße:** Verlust bis Stop (gerechnet ab Kauflimit, inkl. Spread, Slippage, Währungsgebühr, Fixgebühren) ≤ **1,0 % des Portfoliowerts**; Position ≤ 20 % des Portfolios; Kosten ≤ freie Barmittel (**kein Hebel, keine Kredite, keine Leerverkäufe**); Mindestposition 300 €.
- **Pause:** Fällt das Portfolio ≥ 10 % unter seinen Höchststand, werden keine neuen Positionen mehr eröffnet (bestehende Exits laufen weiter). Wiederaufnahme nur durch eine dokumentierte manuelle Freigabe in `papertrading/freigabe.json`.

## Kosten-/Ausführungsannahmen (Annahmen, keine Brokerzusage)
Gebühr 1 € je Order, halber Spread 0,05 %, Slippage 0,05 %, Währungsumrechnung 0,25 % je Richtung, 2 % deterministisch simulierte Ablehnungen (Hash der Order-ID), Ausführung ausschließlich zu Eröffnungs-/Tagesbalken (kein Intraday). Steuern werden nicht berücksichtigt.

## Dokumentationspflicht und Zeitdisziplin
Jede Order wird **vor** ihrer Simulation als `order_plan` im hash-verketteten Journal `papertrading/v1.0/journal.jsonl` festgehalten (Wertpapier, Zeitpunkt, Entscheidungsgrundlage, Orderart, Einstieg, Limit, Stop, Ziel, Stückzahl, Risikogrenze, Datenprüfung, Nachrichtenprüfung, Quellen). Pläne, die erst nach der US-Eröffnung des Ausführungstags dokumentiert wurden, werden verworfen. Nur abgeschlossene Tagesbalken (erst ab 21:45 UTC) zählen. Nachträglich verarbeitete Tage (Ausfall) erzeugen keine neuen Pläne und sind im Journal markiert.

## Abschlussbewertung (vorab festgelegt)
Kennzahlen: Rendite, max. Verlust, Kosten, Trades, Datenqualität, Vergleich mit Benchmark. **Verlängerung um 4 Wochen** (automatisch, Regeln unverändert), wenn < 20 abgeschlossene Trades, < 55 verarbeitete Handelstage oder Datenqualität < 90 %. Sonst „Kriterien erfüllt“ nur bei Mehrrendite ≥ 2 Prozentpunkte nach Kosten und max. Verlust ≤ 15 %. Auch dann gilt: 12 Wochen belegen keine dauerhafte Wirksamkeit.
