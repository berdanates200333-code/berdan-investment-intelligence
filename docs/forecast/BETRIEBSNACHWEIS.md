# Betriebsnachweis (Stand 03.11.2026, 16:30 UTC) – nur belegte Fakten

| Kettenglied | Beleg | Status |
|---|---|---|
| Marktpreise geladen (Yahoo + Zweitquelle Nasdaq/StockAnalysis, Rohantwort-Hashes) | `forecast/universum_status.json` (Lauf #5, 35 von 38 Instrumenten zugelassen, EUNL.DE Stufe A) | belegt |
| Benchmark festgeschrieben | `forecast/benchmark_entscheidung.json` (EUNL.DE, 16:25 UTC) | belegt |
| Prognosen vor Stichtag eingegangen | 4 Pilotprognosen 14:17 UTC vor US-Eröffnung 14:30 UTC (Hash-Kette, Pins) | belegt (Pilot) |
| Orders korrekt geplant | Probelauf `forecast/probelauf2/<ki>/konto/handel.jsonl` (`order_plan` für beide Konten, gleiche Daten) | belegt (Probelauf) |
| Ausführung simuliert | Probelauf-Order wird wegen Dokumentation nach Eröffnung verworfen (korrekt); gültiger Zyklus frühestens mit dem Lauf nach der Sitzung 04.11. | **offen** |
| Journale gespeichert, Folgetag fortgeschrieben | Journal-Kette intakt; Fortschreibung erst am 04.11. nachweisbar | **offen** |
| Automatische Übergabe beider KIs an 2 Handelstagen | keine Belege | **offen** |
| Produktiver Wettbewerbszyklus live | nur Ende-zu-Ende-Test; live erst nach Start | **offen** |
