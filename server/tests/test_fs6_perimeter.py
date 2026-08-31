"""FS6 — reports, ICMP, SNMP PDU, docker connector helpers."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

ROOT = Path(__file__).resolve().parents[2]
SERVER = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(SERVER)):
    if p not in sys.path:
        sys.path.insert(0, p)

from src.report_service import fleet_rows, to_csv, to_pdf  # noqa: E402
from src.network_probe import icmp_ping, _snmp_get_sysdescr_v2c, probe_device  # noqa: E402
from src.connector_service import probe_docker  # noqa: E402


def test_report_csv_and_pdf():
    class A:
        id = "a1"
        hostname = "h1"
        status = "active"
        os = "linux"
        location = "DLA"
        group_id = None
        last_communication = None
        agent_cpu_percent = 0.5
        agent_ram_mb = 80

    class Al:
        agent_id = "a1"
        status = type("S", (), {"value": "open"})()

    rows = fleet_rows([A()], [Al()])
    csv_bytes = to_csv(rows)
    assert b"hostname" in csv_bytes
    assert b"h1" in csv_bytes
    pdf = to_pdf("Test", rows)
    assert pdf.startswith(b"%PDF")
    assert b"%%EOF" in pdf


def test_icmp_ping_mocked():
    with patch("src.network_probe.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        status, rtt, err = icmp_ping("127.0.0.1")
        assert status == "up"
        assert err is None
        assert rtt is not None


def test_snmp_timeout_mocked():
    with patch("src.network_probe.socket.socket") as sock_cls:
        sock = MagicMock()
        sock_cls.return_value = sock
        sock.recvfrom.side_effect = __import__("socket").timeout()
        status, descr, err = _snmp_get_sysdescr_v2c("192.0.2.1", "public")
        assert status == "down"
        assert descr is None
        assert "timeout" in (err or "").lower()


def test_probe_device_combines():
    with patch("src.network_probe.icmp_ping", return_value=("up", 12.0, None)), patch(
        "src.network_probe._snmp_get_sysdescr_v2c", return_value=("up", "Cisco IOS", None)
    ):
        result = probe_device("192.0.2.1")
        assert result["icmp_status"] == "up"
        assert result["snmp_status"] == "up"
        assert result["sys_descr"] == "Cisco IOS"


def test_docker_probe_down():
    with patch("src.connector_service.request.urlopen", side_effect=OSError("nope")):
        result = probe_docker("http://127.0.0.1:9")
        assert result["status"] in ("down", "unknown")
