"""Tests for disk partition collection and alert mount selection."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[2]
AGENT_SRC = Path(__file__).resolve().parents[1] / "src"
for p in (str(ROOT), str(AGENT_SRC)):
    if p not in sys.path:
        sys.path.insert(0, p)

from disk_metrics import collect_disk_partitions, normalize_mount  # noqa: E402


def test_normalize_mount_windows():
    assert normalize_mount("c:") == "C:\\"
    assert normalize_mount("/var") == "/var"


def test_collect_disk_partitions_primary_only_alert():
    fake_usage = MagicMock(percent=72.0, total=100 * 1024**3, used=72 * 1024**3, free=28 * 1024**3)
    parts = [
        MagicMock(mountpoint="/", fstype="ext4"),
        MagicMock(mountpoint="/var", fstype="ext4"),
    ]
    with patch("disk_metrics.psutil.disk_partitions", return_value=parts), patch(
        "disk_metrics.psutil.disk_usage", return_value=fake_usage
    ):
        summary, disks = collect_disk_partitions({"path": "/", "alert_mounts": []})

    assert summary["disk_mount"] == "/"
    assert len(disks) == 2
    assert sum(1 for d in disks if d["alert"]) == 1
    assert next(d for d in disks if d["mount"] == "/")["alert"] is True
    assert next(d for d in disks if d["mount"] == "/var")["alert"] is False
    assert "letter" in disks[0]
    assert "label" in disks[0]
    assert "name" in disks[0]


def test_collect_disk_partitions_selective_alert_mounts():
    fake_usage = MagicMock(percent=50.0, total=50 * 1024**3, used=25 * 1024**3, free=25 * 1024**3)
    parts = [
        MagicMock(mountpoint="/", fstype="ext4"),
        MagicMock(mountpoint="/data", fstype="ext4"),
    ]
    with patch("disk_metrics.psutil.disk_partitions", return_value=parts), patch(
        "disk_metrics.psutil.disk_usage", return_value=fake_usage
    ):
        _, disks = collect_disk_partitions({"path": "/", "alert_mounts": ["/data"]})

    assert next(d for d in disks if d["mount"] == "/")["alert"] is False
    assert next(d for d in disks if d["mount"] == "/data")["alert"] is True
