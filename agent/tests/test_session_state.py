"""session.json persistence for reconnect without a dashboard mismatch."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AGENT_SRC = Path(__file__).resolve().parents[1] / "src"
for p in (str(ROOT), str(AGENT_SRC)):
    if p not in sys.path:
        sys.path.insert(0, p)

from session_state import SessionState  # noqa: E402


def test_session_roundtrip(tmp_path):
    path = tmp_path / "session.json"
    state = SessionState(path)
    state.save(
        server_url="http://127.0.0.1:8443",
        machine_id="mid-1",
        agent_id="agt-1",
        auth_key="secret-key",
        last_error=None,
        consecutive_failures=0,
        buffer_records=2,
        connected=True,
    )
    data = state.load()
    assert data["machine_id"] == "mid-1"
    assert data["auth_key"] == "secret-key"
    assert data["connected"] is True
    assert data["last_success_at"]


def test_session_keeps_last_success_on_failure(tmp_path):
    path = tmp_path / "session.json"
    state = SessionState(path)
    state.save(
        server_url="http://127.0.0.1:8443",
        machine_id="mid-1",
        agent_id="agt-1",
        auth_key="secret-key",
        connected=True,
    )
    first = json.loads(path.read_text(encoding="utf-8"))["last_success_at"]
    state.save(
        server_url="http://127.0.0.1:8443",
        machine_id="mid-1",
        agent_id="agt-1",
        auth_key=None,
        last_error="HTTP 500",
        consecutive_failures=3,
        connected=False,
    )
    data = state.load()
    assert data["connected"] is False
    assert data["last_error"] == "HTTP 500"
    assert data["last_success_at"] == first
