"""FS9 — task.v1 signing, approval chain, heartbeat dispatch (SEC-005)."""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from src.config import settings
from src.models import ActionApproval, Agent, RemoteTask

# Plugins allowed for Lot 2 L1 execution (agent also enforces)
ALLOWLIST_PLUGINS = {
    "health.check",
    "service.manage",
    "inventory.snapshot",
    "metrics.on_demand",
    "pci.hygiene",  # Lot 2 — PCI hygiene checklist (read-only)
}

# Plugins that always require human approval when dry_run=False
APPROVAL_REQUIRED_PLUGINS = {
    "service.manage",
}


def _utcnow() -> datetime:
    return datetime.utcnow()


def sign_task_payload(task_id: str, agent_id: str, plugin: str, expires_at: datetime) -> str:
    secret = (settings.secret_key or "dev").encode("utf-8")
    exp = expires_at.replace(tzinfo=None).isoformat() if expires_at.tzinfo else expires_at.isoformat()
    msg = f"{task_id}|{agent_id}|{plugin}|{exp}".encode("utf-8")
    return hmac.new(secret, msg, hashlib.sha256).hexdigest()


def verify_task_signature(task_id: str, agent_id: str, plugin: str, expires_at: datetime, signature: str) -> bool:
    expected = sign_task_payload(task_id, agent_id, plugin, expires_at)
    return hmac.compare_digest(expected, signature or "")


def _append_audit(task: RemoteTask, actor: str, action: str, note: str = "") -> None:
    trail = []
    try:
        trail = json.loads(task.audit_trail or "[]")
    except Exception:
        trail = []
    trail.append(
        {
            "at": _utcnow().isoformat() + "Z",
            "actor": actor,
            "action": action,
            "note": note,
        }
    )
    task.audit_trail = json.dumps(trail)


def create_task(
    db: Session,
    *,
    agent_id: str,
    plugin: str,
    input_data: Dict[str, Any],
    dry_run: bool,
    requested_by: str,
    issued_by: str = "user",
    ttl_minutes: int = 30,
    force_approval: bool = False,
) -> Tuple[RemoteTask, Optional[ActionApproval]]:
    if plugin not in ALLOWLIST_PLUGINS:
        raise ValueError(f"Plugin not allow-listed: {plugin}")
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent or agent.status != "active":
        raise ValueError("Agent introuvable ou inactif")

    task_id = str(uuid.uuid4())
    expires = _utcnow() + timedelta(minutes=ttl_minutes)
    needs_approval = force_approval or (not dry_run and plugin in APPROVAL_REQUIRED_PLUGINS)
    status = "pending_approval" if needs_approval else "queued"
    signature = sign_task_payload(task_id, agent_id, plugin, expires)

    task = RemoteTask(
        id=task_id,
        agent_id=agent_id,
        plugin=plugin,
        input_json=json.dumps(input_data or {}),
        dry_run=dry_run,
        status=status,
        issued_by=issued_by,
        requested_by=requested_by,
        signature=signature,
        expires_at=expires,
    )
    _append_audit(task, requested_by, "created", f"dry_run={dry_run}")
    db.add(task)

    approval = None
    if needs_approval:
        approval = ActionApproval(
            id=str(uuid.uuid4()),
            task_id=task_id,
            status="pending",
            requested_by=requested_by,
        )
        task.approval_ref = approval.id
        _append_audit(task, requested_by, "awaiting_approval", approval.id)
        db.add(approval)

    db.commit()
    db.refresh(task)
    try:
        from src.messaging_service import MessagingService

        status = "pending_approval" if needs_approval else "queued"
        MessagingService.send_task_notification(
            plugin=plugin,
            status=status,
            message=f"Action {plugin} {status} sur {agent.hostname}",
            db=db,
            agent=agent,
            task_id=task.id,
            dry_run=dry_run,
            requested_by=requested_by,
        )
    except Exception:
        pass
    return task, approval


def decide_approval(
    db: Session,
    approval_id: str,
    *,
    decide: str,
    decided_by: str,
    comment: str = "",
) -> ActionApproval:
    row = db.query(ActionApproval).filter(ActionApproval.id == approval_id).first()
    if not row:
        raise ValueError("Approbation introuvable")
    if row.status != "pending":
        raise ValueError("Approbation déjà tranchée")
    if decide not in ("approved", "denied"):
        raise ValueError("Décision invalide")
    row.status = decide
    row.decided_by = decided_by
    row.comment = comment
    row.decided_at = _utcnow()
    task = db.query(RemoteTask).filter(RemoteTask.id == row.task_id).first()
    if task:
        if decide == "approved":
            task.status = "queued"
            _append_audit(task, decided_by, "approved", comment)
        else:
            task.status = "denied"
            task.completed_at = _utcnow()
            _append_audit(task, decided_by, "denied", comment)
    db.commit()
    db.refresh(row)
    try:
        from src.messaging_service import MessagingService

        agent = db.query(Agent).filter(Agent.id == task.agent_id).first() if task else None
        MessagingService.send_task_notification(
            plugin=task.plugin if task else "unknown",
            status=decide,
            message=comment or f"Action {decide}",
            db=db,
            agent=agent,
            task_id=row.task_id,
            dry_run=bool(task.dry_run) if task else False,
            requested_by=decided_by,
        )
    except Exception:
        pass
    return row


def pending_tasks_for_agent(db: Session, agent_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    now = _utcnow()
    rows = (
        db.query(RemoteTask)
        .filter(
            RemoteTask.agent_id == agent_id,
            RemoteTask.status == "queued",
            RemoteTask.expires_at > now,
        )
        .order_by(RemoteTask.created_at.asc())
        .limit(limit)
        .all()
    )
    out = []
    for t in rows:
        wire = {
            "schema": "task.v1",
            "task_id": t.id,
            "issued_by": t.issued_by or "user",
            "signature": t.signature,
            "plugin": t.plugin,
            "input": json.loads(t.input_json or "{}"),
            "dry_run": bool(t.dry_run),
            "approval_ref": t.approval_ref,
            "expires_at": t.expires_at.replace(tzinfo=timezone.utc).isoformat()
            if t.expires_at.tzinfo is None
            else t.expires_at.isoformat(),
            "agent_id": t.agent_id,
        }
        t.status = "dispatched"
        t.dispatched_at = now
        _append_audit(t, "system", "dispatched")
        out.append(wire)
    if rows:
        db.commit()
    return out


def apply_task_results(db: Session, agent_id: str, results: List[Dict[str, Any]]) -> int:
    accepted = 0
    for item in results or []:
        task_id = str(item.get("task_id") or "")
        if not task_id:
            continue
        task = db.query(RemoteTask).filter(RemoteTask.id == task_id, RemoteTask.agent_id == agent_id).first()
        if not task:
            continue
        status = str(item.get("status") or "failed")
        # Map protocol statuses
        if status == "dry_run":
            task.status = "dry_run"
        elif status in ("succeeded", "failed", "rejected", "expired", "running"):
            task.status = status
        else:
            task.status = "failed"
        task.result_json = json.dumps(item)
        task.rejection_reason = item.get("rejection_reason")
        task.completed_at = _utcnow()
        _append_audit(task, "agent", "result", status)
        accepted += 1
        try:
            from src.messaging_service import MessagingService

            agent = db.query(Agent).filter(Agent.id == agent_id).first()
            MessagingService.send_task_notification(
                plugin=task.plugin,
                status=task.status,
                message=item.get("rejection_reason") or f"Résultat {task.status}",
                db=db,
                agent=agent,
                task_id=task.id,
                dry_run=bool(task.dry_run),
            )
        except Exception:
            pass
    if accepted:
        db.commit()
    return accepted


def serialize_task(t: RemoteTask) -> Dict[str, Any]:
    return {
        "id": t.id,
        "agent_id": t.agent_id,
        "plugin": t.plugin,
        "input": json.loads(t.input_json or "{}"),
        "dry_run": t.dry_run,
        "status": t.status,
        "issued_by": t.issued_by,
        "requested_by": t.requested_by,
        "approval_ref": t.approval_ref,
        "expires_at": t.expires_at,
        "result": json.loads(t.result_json) if t.result_json else None,
        "rejection_reason": t.rejection_reason,
        "audit_trail": json.loads(t.audit_trail or "[]"),
        "created_at": t.created_at,
        "dispatched_at": t.dispatched_at,
        "completed_at": t.completed_at,
    }
