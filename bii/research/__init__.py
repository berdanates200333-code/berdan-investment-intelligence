"""Research-Desk (Phase 2): Unternehmensprofile, Quellenüberwachung, Ereigniserkennung, Bewertung.

Trennung der Verantwortung:
- Python (dieses Paket) holt Daten aus offiziellen, kostenfreien Quellen, dokumentiert jede Quelle,
  erkennt neue Ereignisse, entfernt Dubletten, rechnet Kennzahlen/Bewertungen und prüft
  maschinenlesbare Thesen-Bedingungen. Das sind REGELN, keine KI.
- KI-Analysen (Claude) arbeiten ausschließlich auf den hier gespeicherten Belegen
  (research/desk/evidence, research/desk/findings.jsonl) und werden getrennt gekennzeichnet.
Keine Orders, keine Broker-Verbindung, keine kostenpflichtigen APIs.
"""
