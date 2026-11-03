import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture(autouse=True)
def _isolate_phase(monkeypatch):
    """Tests dürfen nicht vom realen Wettbewerbsstatus des Repos abhängen (forecast/wettbewerb.json)."""
    from bii.forecast import jr
    monkeypatch.setattr(jr, "phase", lambda: "pilot")
