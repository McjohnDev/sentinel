"""FS9 — task signing + approval transitions."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

ROOT = Path(__file__).resolve().parents[2]
SERVER = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(SERVER)):
    if p not in sys.path:
        sys.path.insert(0, p)

from src.task_service import (  # noqa: E402
    sign_task_payload,
    verify_task_signature,
    ALLOWLIST_PLUGINS,
)


def test_hmac_sign_verify():
    exp = datetime.utcnow() + timedelta(minutes=10)
    sig = sign_task_payload("tid", "aid", "health.check", exp)
    assert verify_task_signature("tid", "aid", "health.check", exp, sig)
    assert not verify_task_signature("tid", "aid", "health.check", exp, "deadbeef")


def test_allowlist_includes_service_manage():
    assert "service.manage" in ALLOWLIST_PLUGINS
    assert "health.check" in ALLOWLIST_PLUGINS
    assert "pci.hygiene" in ALLOWLIST_PLUGINS
