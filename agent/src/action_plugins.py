"""Lot 2 L1 action plugins — allow-listed, dry-run aware (AGT-060+)."""

from __future__ import annotations

import platform
import time
from typing import Any, Dict, List, Optional

from shared.protocols.task import TaskResultV1, TaskV1

ALLOWLIST = {
    "health.check",
    "service.manage",
    "inventory.snapshot",
    "metrics.on_demand",
    "pci.hygiene",  # Lot 2 — PCI DSS–aligned hygiene (not AoC/ASV)
}


def _ms_since(t0: float) -> int:
    return max(0, int((time.perf_counter() - t0) * 1000))


def execute_task(task: TaskV1, *, capability_level: str = "L0") -> TaskResultV1:
    t0 = time.perf_counter()
    if capability_level.upper() != "L1":
        return TaskResultV1(
            schema="task.result.v1",
            task_id=task.task_id,
            status="rejected",
            duration_ms=_ms_since(t0),
            rejection_reason="agent capability L0 — actions are not enabled (Lot 2)",
            output={"plugin": task.plugin, "dry_run": task.dry_run},
        )
    if task.plugin not in ALLOWLIST:
        return TaskResultV1(
            schema="task.result.v1",
            task_id=task.task_id,
            status="rejected",
            duration_ms=_ms_since(t0),
            rejection_reason=f"plugin not allow-listed: {task.plugin}",
            output={},
        )

    try:
        if task.plugin == "health.check":
            out = _health_check(task.input or {}, dry_run=task.dry_run)
        elif task.plugin == "service.manage":
            out = _service_manage(task.input or {}, dry_run=task.dry_run)
        elif task.plugin == "inventory.snapshot":
            out = _inventory(task.input or {}, dry_run=task.dry_run)
        elif task.plugin == "metrics.on_demand":
            out = _metrics_on_demand(task.input or {}, dry_run=task.dry_run)
        elif task.plugin == "pci.hygiene":
            from pci_hygiene import run_pci_hygiene

            out = run_pci_hygiene(task.input or {}, dry_run=task.dry_run)
        else:
            out = {"ok": False}
        status = "dry_run" if task.dry_run else "succeeded"
        return TaskResultV1(
            schema="task.result.v1",
            task_id=task.task_id,
            status=status,
            duration_ms=_ms_since(t0),
            exit_code=0,
            output=out,
            audit_ref=str(task.approval_ref) if task.approval_ref else None,
        )
    except Exception as exc:
        return TaskResultV1(
            schema="task.result.v1",
            task_id=task.task_id,
            status="failed",
            duration_ms=_ms_since(t0),
            exit_code=1,
            output={"error": str(exc)},
            stderr_truncated=str(exc)[:2000],
        )


def _health_check(inp: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    return {
        "planned": True,
        "dry_run": dry_run,
        "host": platform.node(),
        "system": platform.system(),
        "release": platform.release(),
        "checks": inp.get("checks") or ["ping"],
        "result": "ok",
    }


def _service_manage(inp: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    service = str(inp.get("service") or "")
    operation = str(inp.get("operation") or "status")
    if not service:
        raise ValueError("service required")
    if operation not in ("status", "start", "stop", "restart"):
        raise ValueError("invalid operation")
    # Real start/stop/restart only simulated as planned change in Lot 2 starter
    # (safe default — never touches live services without further CBC allow-list)
    return {
        "service": service,
        "operation": operation,
        "dry_run": dry_run,
        "executed": False if dry_run else False,
        "message": (
            f"Would {operation} service '{service}'"
            if dry_run
            else f"Lot 2 starter: {operation} on '{service}' recorded (execution gated pending CBC allow-list)"
        ),
    }


def _inventory(inp: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    return {
        "dry_run": dry_run,
        "hostname": platform.node(),
        "os": platform.platform(),
        "python": platform.python_version(),
        "machine": platform.machine(),
    }


def _metrics_on_demand(inp: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    families = inp.get("families") or ["cpu", "memory"]
    return {"dry_run": dry_run, "families": families, "collected": False if dry_run else True}


def handle_incoming_tasks(raw_tasks: list, *, capability_level: str = "L0") -> list[dict]:
    results: List[dict] = []
    for item in raw_tasks or []:
        task = TaskV1.model_validate(item)
        results.append(execute_task(task, capability_level=capability_level).to_wire_dict())
    return results
