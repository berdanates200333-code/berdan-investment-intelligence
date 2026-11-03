---
description: Tages-Cockpit Prognosewettbewerb (Portfolio, Einschätzungen, Kursprognosen, Bewertungen, G/V, Systemstatus) direkt im Chat
---
Zeige dem Nutzer das Tages-Cockpit, ohne dass er etwas auf GitHub tun muss. Nur virtuell, kein Echtgeld.
1. `git pull` (Ergebnisse der Automatik holen).
2. Führe `python scripts/fc_cockpit.py claude` aus und gib die Ausgabe als gut lesbare Tabellen im Chat wieder. Ergänze höchstens 3 Sätze Erläuterung: was ist heute neu/fällig, größter Gewinn/Verlust, technische Auffälligkeiten (Datenstufen, Startschranke).
3. Vergleich mit ChatGPT (`python scripts/fc_cockpit.py vergleich`) nur auf ausdrücklichen Wunsch UND erst, nachdem Claudes eigene Tagesprognose des Tages abgegeben ist.
4. Fehlt etwas oder ist der Status rot: nenne den konkreten Blocker, nicht „läuft“. Behaupte nie eine funktionierende Automatik ohne Beleg im Cockpit-Status.
