"""L0/L1 task handling — task.v1 envelope (AGT-010 / Lot 2)."""

from __future__ import annotations

from action_plugins import execute_task, handle_incoming_tasks  # noqa: F401
from shared.protocols.task import TaskResultV1, TaskV1


L0_REJECTION = "agent capability L0 — actions are not enabled (Lot 2)"


def reject_l0_task(task: TaskV1) -> TaskResultV1:
    return execute_task(task, capability_level="L0")
