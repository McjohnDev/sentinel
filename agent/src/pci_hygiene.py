"""PCI DSS–aligned hygiene checks (Lot 2) — NOT a QSA / ASV certification.

Read-only host probes mapped to high-level PCI themes. Score is hygiene only.
"""

from __future__ import annotations

import platform
import shutil
import subprocess
from typing import Any, Dict, List, Optional, Tuple

# Optional watched processes often expected on payment estate (override via task input)
DEFAULT_SECURITY_PROCESSES = {
    "windows": ["MsMpEng", "Sense", "CSFalconService", "CrowdStrike"],
    "linux": ["clamd", "falcon-sensor", "auditd", "chronyd", "systemd-timesyncd"],
    "darwin": ["Falcon", "Little Snitch"],
}

# Cleartext / high-risk listening ports (PCI Req. 1 / 2 hygiene)
RISKY_PORTS = {21: "ftp", 23: "telnet", 69: "tftp", 111: "rpcbind", 445: "smb", 3389: "rdp"}


def _ok(check_id: str, title: str, pci_ref: str, detail: str, pass_: bool, weight: int = 1) -> Dict[str, Any]:
    return {
        "id": check_id,
        "title": title,
        "pci_ref": pci_ref,
        "pass": pass_,
        "weight": weight,
        "detail": detail,
    }


def _net_connections() -> List[Any]:
    try:
        import psutil

        return list(psutil.net_connections(kind="inet"))
    except Exception:
        return []


def _process_names() -> set[str]:
    names: set[str] = set()
    try:
        import psutil

        for p in psutil.process_iter(["name"]):
            n = (p.info.get("name") or "").strip()
            if n:
                names.add(n.lower())
    except Exception:
        pass
    return names


def _disk_primary_ok() -> Tuple[bool, str]:
    try:
        import psutil

        path = "C:\\" if platform.system().lower() == "windows" else "/"
        u = psutil.disk_usage(path)
        free_pct = 100.0 - float(u.percent)
        return free_pct >= 15.0, f"{path} free≈{free_pct:.0f}%"
    except Exception as exc:
        return False, f"disk check failed: {exc}"


def _logging_ok() -> Tuple[bool, str]:
    system = platform.system().lower()
    if system == "windows":
        return True, "Windows Event Log assumed available (agent winevt path)"
    if system == "linux":
        if shutil.which("journalctl"):
            return True, "journalctl present"
        return False, "journalctl not found"
    return True, f"logging probe soft-pass on {system}"


def _time_sync_ok(procs: set[str]) -> Tuple[bool, str]:
    system = platform.system().lower()
    if system == "windows":
        hit = any(x in procs for x in ("svchost.exe",))  # W32Time runs under svchost — soft
        # Better: query service if possible
        try:
            r = subprocess.run(
                ["sc", "query", "W32Time"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            running = "RUNNING" in (r.stdout or "").upper()
            return running, "W32Time " + ("RUNNING" if running else "not running")
        except Exception:
            return hit, "W32Time query unavailable (soft)"
    for name in ("chronyd", "ntpd", "systemd-timesyncd", "timed"):
        if name in procs or f"{name}.exe" in procs:
            return True, f"time sync process: {name}"
    return False, "no chrony/ntp/timesyncd process seen"


def _firewall_hint() -> Tuple[bool, str]:
    system = platform.system().lower()
    try:
        if system == "windows":
            r = subprocess.run(
                ["netsh", "advfirewall", "show", "allprofiles"],
                capture_output=True,
                text=True,
                timeout=8,
            )
            lines = [ln.strip() for ln in (r.stdout or "").splitlines()]
            states = [ln for ln in lines if ln.lower().startswith("state")]
            on = any(ln.lower().endswith("on") for ln in states)
            return on, "Windows Firewall: " + (", ".join(states[:3]) or "unknown")
        if system == "linux":
            if shutil.which("ufw"):
                r = subprocess.run(["ufw", "status"], capture_output=True, text=True, timeout=5)
                active = "active" in (r.stdout or "").lower()
                return active, (r.stdout or "")[:120]
            if shutil.which("firewall-cmd"):
                r = subprocess.run(
                    ["firewall-cmd", "--state"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                return "running" in (r.stdout or "").lower(), (r.stdout or "").strip()
            return False, "no ufw/firewalld detected"
    except Exception as exc:
        return False, f"firewall probe failed: {exc}"
    return True, f"firewall soft-pass on {system}"


def _risky_listeners(conns: List[Any]) -> Tuple[bool, str]:
    found: List[str] = []
    for c in conns:
        try:
            if getattr(c, "status", None) != "LISTEN":
                continue
            port = int(c.laddr.port) if c.laddr else -1
            if port in RISKY_PORTS:
                found.append(f"{port}/{RISKY_PORTS[port]}")
        except Exception:
            continue
    if found:
        return False, "listening: " + ", ".join(sorted(set(found)))
    return True, "no ftp/telnet/tftp/rpc/smb/rdp listeners seen"


def _security_agent_present(procs: set[str], watched: List[str]) -> Tuple[bool, str]:
    if not watched:
        return True, "no security process list configured (soft-pass)"
    hits = [w for w in watched if w.lower() in procs or any(w.lower() in p for p in procs)]
    if hits:
        return True, "found: " + ", ".join(hits[:5])
    return False, "none of " + ", ".join(watched[:6]) + " seen"


def run_pci_hygiene(inp: Optional[Dict[str, Any]] = None, *, dry_run: bool = False) -> Dict[str, Any]:
    """Execute read-only PCI hygiene checklist. Safe for dry-run and live (no mutations)."""
    inp = inp or {}
    system = platform.system().lower()
    family = "windows" if system == "windows" else ("darwin" if system == "darwin" else "linux")
    watched = inp.get("security_processes")
    if not isinstance(watched, list) or not watched:
        watched = DEFAULT_SECURITY_PROCESSES.get(family, [])

    procs = _process_names()
    conns = _net_connections()

    checks: List[Dict[str, Any]] = []

    # Req 1 — network: risky listeners
    ok, detail = _risky_listeners(conns)
    checks.append(_ok("net.risky_ports", "No cleartext/high-risk listeners", "Req 1 / 2", detail, ok, 2))

    # Req 1 — firewall
    ok, detail = _firewall_hint()
    checks.append(_ok("net.firewall", "Host firewall enabled", "Req 1", detail, ok, 2))

    # Req 2 — inventory identity
    checks.append(
        _ok(
            "inv.identity",
            "Host identity collectable",
            "Req 2",
            f"{platform.node()} · {platform.platform()}",
            bool(platform.node()),
            1,
        )
    )

    # Req 5 — malware / EDR process presence
    ok, detail = _security_agent_present(procs, [str(x) for x in watched])
    checks.append(_ok("sec.endpoint", "Security / AV / EDR process", "Req 5", detail, ok, 2))

    # Req 6 — time sync
    ok, detail = _time_sync_ok(procs)
    checks.append(_ok("ops.time", "Time synchronization", "Req 6 / 10", detail, ok, 1))

    # Req 10 — logging
    ok, detail = _logging_ok()
    checks.append(_ok("ops.logging", "Local logging capability", "Req 10", detail, ok, 2))

    # Continuity / ops hygiene (support Req 12 ops discipline)
    ok, detail = _disk_primary_ok()
    checks.append(_ok("ops.disk", "Primary volume free ≥ 15%", "Ops hygiene", detail, ok, 1))

    # Agent itself reporting
    checks.append(
        _ok(
            "agt.l1",
            "Remote hygiene task executed",
            "Ops",
            "pci.hygiene Lot-2 action",
            True,
            1,
        )
    )

    total_w = sum(int(c["weight"]) for c in checks) or 1
    pass_w = sum(int(c["weight"]) for c in checks if c["pass"])
    score = round(100.0 * pass_w / total_w, 1)
    failed = [c for c in checks if not c["pass"]]

    if score >= 85:
        grade = "good"
    elif score >= 60:
        grade = "fair"
    else:
        grade = "poor"

    return {
        "schema": "pci.hygiene.v1",
        "dry_run": dry_run,
        "executed": True,  # checks always run; dry_run does not skip probes (read-only)
        "disclaimer": (
            "PCI Hygiene score only — not a PCI DSS Attestation of Compliance, "
            "ASV scan, or QSA assessment."
        ),
        "hostname": platform.node(),
        "os": platform.system(),
        "score": score,
        "grade": grade,
        "passed": len(checks) - len(failed),
        "failed": len(failed),
        "total": len(checks),
        "checks": checks,
        "failed_ids": [c["id"] for c in failed],
    }
