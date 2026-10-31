"""Unveränderlichkeit: Bereits protokollierte FT1-Einträge sind hier festgeschrieben.

Jeder neue Lauf darf das Journal nur ERWEITERN. Ändert sich ein bestehender Eintrag
(oder wird einer gelöscht), schlägt dieser Test fehl und der Workflow meldet einen Fehler.
Neue Pins werden nur ergänzt, nie geändert.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bii import journal  # noqa: E402

PINS = {
    1: ("FT1-BENCH-WORLD-start", "6fb7f5eceb03519a94343626212639c0369af67cba3a4823e683b14c36989c0c"),
    2: ("FT1-TREND-WORLD-2026-09", "e767beed61ae329934ca1a7afbb5dbfc2540b6edbb91ed3768d0d97fa8e31dfa"),
    3: ("FT1-TREND-GOLD-2026-09", "07f6043d1ba5fc5422b8af28e5ec76559919316833e13bad43027742eb1e9778"),
    4: ("FT1-TREND-BTC-2026-09", "e2abd93e7f91335e49a7d1d8ff4cd3d7b9eceb6d1d9f628cf82282eb18677df6"),
    5: (None, "a1287eca6f33187cec64b685eda8fd3827254cce72744f8e495aa351f5ddd752"),  # Regeländerung v1.1
}


def test_journal_chain_intact():
    ok, msg = journal.verify()
    assert ok, msg


def test_pinned_entries_unchanged():
    lines = journal.JOURNAL.read_text().splitlines()
    for seq, (sid, h) in PINS.items():
        e = json.loads(lines[seq - 1])
        assert e["seq"] == seq and e["signal_id"] == sid and e["hash"] == h, f"Eintrag {seq} verändert"
