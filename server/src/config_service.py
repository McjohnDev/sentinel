"""AGT-008 — machine groups and versioned remote config."""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict, Optional, Tuple

from sqlalchemy.orm import Session

from src.models import Agent, ConfigRevision, MachineGroup


def deep_merge(base: Dict[str, Any], overlay: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(base or {})
    for key, value in (overlay or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = value
    return out


class ConfigService:
    @staticmethod
    def create_group(db: Session, name: str, description: Optional[str] = None) -> MachineGroup:
        group = MachineGroup(
            id=str(uuid.uuid4()),
            name=name.strip(),
            description=description,
            current_version=0,
        )
        db.add(group)
        db.commit()
        db.refresh(group)
        return group

    @staticmethod
    def assign_agent(db: Session, agent_id: str, group_id: Optional[str]) -> Agent:
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            raise ValueError("agent not found")
        if group_id:
            group = db.query(MachineGroup).filter(MachineGroup.id == group_id).first()
            if not group:
                raise ValueError("group not found")
        agent.group_id = group_id
        # Force re-pull of group config after reassignment
        agent.config_version_acked = 0
        db.commit()
        db.refresh(agent)
        return agent

    @staticmethod
    def publish(
        db: Session,
        group_id: str,
        payload: Dict[str, Any],
        *,
        created_by: Optional[str] = None,
        note: Optional[str] = None,
    ) -> ConfigRevision:
        group = db.query(MachineGroup).filter(MachineGroup.id == group_id).first()
        if not group:
            raise ValueError("group not found")
        next_version = int(group.current_version or 0) + 1
        rev = ConfigRevision(
            id=str(uuid.uuid4()),
            group_id=group_id,
            version=next_version,
            payload=json.dumps(payload or {}),
            note=note,
            created_by=created_by,
        )
        group.current_version = next_version
        db.add(rev)
        db.commit()
        db.refresh(rev)
        return rev

    @staticmethod
    def rollback(
        db: Session,
        group_id: str,
        to_version: int,
        *,
        created_by: Optional[str] = None,
    ) -> ConfigRevision:
        old = (
            db.query(ConfigRevision)
            .filter(ConfigRevision.group_id == group_id, ConfigRevision.version == to_version)
            .first()
        )
        if not old:
            raise ValueError("revision not found")
        payload = json.loads(old.payload or "{}")
        return ConfigService.publish(
            db,
            group_id,
            payload,
            created_by=created_by,
            note=f"rollback to v{to_version}",
        )

    @staticmethod
    def pending_for_agent(db: Session, agent: Agent) -> Optional[Tuple[int, Dict[str, Any]]]:
        if not agent.group_id:
            return None
        group = db.query(MachineGroup).filter(MachineGroup.id == agent.group_id).first()
        if not group or not group.current_version:
            return None
        acked = int(agent.config_version_acked or 0)
        if acked >= group.current_version:
            return None
        rev = (
            db.query(ConfigRevision)
            .filter(
                ConfigRevision.group_id == group.id,
                ConfigRevision.version == group.current_version,
            )
            .first()
        )
        if not rev:
            return None
        try:
            payload = json.loads(rev.payload or "{}")
        except json.JSONDecodeError:
            payload = {}
        return group.current_version, payload

    @staticmethod
    def ack(db: Session, agent_id: str, version: int) -> Agent:
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            raise ValueError("agent not found")
        agent.config_version_acked = int(version)
        db.commit()
        db.refresh(agent)
        return agent
