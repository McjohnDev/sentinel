"""FS8 — UAT seed data, DES-004 extinction rules, acceptance pack (Part K / M4)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from src.models import AcceptanceSignOff, CoverageCheck, PilotHost, UatCase

ALLOWED_COVERAGE_STATUS = {
    "planned",
    "delivered",
    "verified_in_production",
    "script_decommissioned",
    "waived",
}

# delivered → verified → decommissioned; waived anytime from planned/delivered
_TRANSITIONS = {
    "planned": {"delivered", "waived"},
    "delivered": {"verified_in_production", "waived"},
    "verified_in_production": {"script_decommissioned"},
    "script_decommissioned": set(),
    "waived": set(),
}

DEFAULT_COVERAGE: List[Dict[str, str]] = [
    {"id": "PS-001", "description": "CPU threshold / utilisation", "plugin": "cpu.collector", "sprint": "FS2", "status": "delivered"},
    {"id": "PS-002", "description": "Disk free space", "plugin": "disk.collector", "sprint": "FS2", "status": "delivered"},
    {"id": "PS-003", "description": "Critical Windows/Linux service", "plugin": "services.collector", "sprint": "FS5", "status": "delivered"},
    {"id": "PS-004", "description": "Watched log / file growth", "plugin": "files.collector", "sprint": "FS5", "status": "delivered"},
    {"id": "PS-005", "description": "Memory utilisation", "plugin": "memory.collector", "sprint": "FS2", "status": "delivered"},
    {"id": "PS-006", "description": "Network IF counters", "plugin": "network.collector", "sprint": "FS2", "status": "delivered"},
    {"id": "PS-007", "description": "Process presence / Top-N", "plugin": "process.collector", "sprint": "FS2", "status": "delivered"},
    {"id": "PS-008", "description": "Agent self footprint", "plugin": "agent.footprint", "sprint": "FS5", "status": "delivered"},
]

DEFAULT_UAT: List[Dict[str, Any]] = [
    # Family 1 — Fleet onboarding
    {"family": 1, "case_id": "UAT-1.01", "title": "Install agent on pilot host", "refs": "AGT-001,AGT-012"},
    {"family": 1, "case_id": "UAT-1.02", "title": "Enrol with single-use token", "refs": "AGT-003,AGT-004"},
    {"family": 1, "case_id": "UAT-1.03", "title": "First heartbeat within 60 s", "refs": "NFR-001"},
    {"family": 1, "case_id": "UAT-1.04", "title": "First metrics visible in dashboard", "refs": "DSH-001,PLT-001"},
    # Family 3 — Alerting E2E
    {"family": 3, "case_id": "UAT-3.01", "title": "Trigger threshold alert (Major+)", "refs": "ALR-001"},
    {"family": 3, "case_id": "UAT-3.02", "title": "Mail API notification received", "refs": "INT-001"},
    {"family": 3, "case_id": "UAT-3.03", "title": "HMAC webhook delivered", "refs": "INT-003"},
    {"family": 3, "case_id": "UAT-3.04", "title": "Acknowledge then resolve", "refs": "ALR-005"},
    {"family": 3, "case_id": "UAT-3.05", "title": "Escalation after duration", "refs": "ALR-006"},
    # Family 4 — Resilience
    {"family": 4, "case_id": "UAT-4.01", "title": "Platform outage → agent buffer fills", "refs": "AGT-005,NFR-006"},
    {"family": 4, "case_id": "UAT-4.02", "title": "Recovery → ordered replay, no loss", "refs": "NFR-006"},
    {"family": 4, "case_id": "UAT-4.03", "title": "Agent restart resumes collection", "refs": "AGT-001"},
    {"family": 4, "case_id": "UAT-4.04", "title": "Network flap tolerated", "refs": "AGT-005"},
    # Family 5 — History & reporting
    {"family": 5, "case_id": "UAT-5.01", "title": "TSDB history query returns points", "refs": "STO-001,DSH-002"},
    {"family": 5, "case_id": "UAT-5.02", "title": "CSV fleet report download", "refs": "DSH-007"},
    {"family": 5, "case_id": "UAT-5.03", "title": "PDF fleet report download", "refs": "DSH-007"},
    {"family": 5, "case_id": "UAT-5.04", "title": "Retention settings applied", "refs": "STO-005"},
]


def ensure_coverage_seed(db: Session) -> int:
    created = 0
    for row in DEFAULT_COVERAGE:
        if db.query(CoverageCheck).filter(CoverageCheck.id == row["id"]).first():
            continue
        db.add(
            CoverageCheck(
                id=row["id"],
                description=row["description"],
                plugin=row["plugin"],
                legacy_script="TBD — CBC inventory",
                hosts="TBD",
                status=row["status"],
                sprint=row["sprint"],
                notes="",
            )
        )
        created += 1
    if created:
        db.commit()
    return created


def ensure_uat_seed(db: Session) -> int:
    import uuid

    created = 0
    for row in DEFAULT_UAT:
        if db.query(UatCase).filter(UatCase.case_id == row["case_id"]).first():
            continue
        db.add(
            UatCase(
                id=str(uuid.uuid4()),
                family=row["family"],
                case_id=row["case_id"],
                title=row["title"],
                requirement_refs=row["refs"],
                status="pending",
            )
        )
        created += 1
    if created:
        db.commit()
    return created


def can_transition(current: str, new: str) -> bool:
    if new not in ALLOWED_COVERAGE_STATUS:
        return False
    if current == new:
        return True
    return new in _TRANSITIONS.get(current, set())


def apply_coverage_status(check: CoverageCheck, new_status: str) -> None:
    if not can_transition(check.status, new_status):
        raise ValueError(f"Invalid transition {check.status} → {new_status}")
    check.status = new_status
    now = datetime.utcnow()
    if new_status == "verified_in_production":
        check.verified_at = now
    if new_status == "script_decommissioned":
        check.decommissioned_at = now


def coverage_summary(db: Session) -> Dict[str, Any]:
    ensure_coverage_seed(db)
    rows = db.query(CoverageCheck).order_by(CoverageCheck.id.asc()).all()
    by_status: Dict[str, int] = {}
    for r in rows:
        by_status[r.status] = by_status.get(r.status, 0) + 1
    open_musts = [
        r.id
        for r in rows
        if r.status not in ("verified_in_production", "script_decommissioned", "waived")
    ]
    return {
        "total": len(rows),
        "by_status": by_status,
        "open_must_check_ids": open_musts,
        "zero_open_musts": len(open_musts) == 0,
        "extinction_ready": all(
            r.status in ("script_decommissioned", "waived") for r in rows
        ),
    }


def uat_summary(db: Session) -> Dict[str, Any]:
    ensure_uat_seed(db)
    rows = db.query(UatCase).order_by(UatCase.family.asc(), UatCase.case_id.asc()).all()
    families: Dict[int, Dict[str, int]] = {}
    for r in rows:
        bucket = families.setdefault(r.family, {"total": 0, "pass": 0, "fail": 0, "pending": 0, "blocked": 0, "waived": 0})
        bucket["total"] += 1
        bucket[r.status] = bucket.get(r.status, 0) + 1
    lot1_families = {1, 3, 4, 5}
    pending = [r.case_id for r in rows if r.family in lot1_families and r.status in ("pending", "fail", "blocked")]
    return {
        "families": families,
        "open_case_ids": pending,
        "lot1_uat_complete": len(pending) == 0,
    }


def build_acceptance_pack(db: Session) -> Dict[str, Any]:
    """FS8-06 — requirement → test → evidence snapshot."""
    ensure_coverage_seed(db)
    ensure_uat_seed(db)
    cov = coverage_summary(db)
    uat = uat_summary(db)
    cases = db.query(UatCase).order_by(UatCase.family.asc(), UatCase.case_id.asc()).all()
    checks = db.query(CoverageCheck).order_by(CoverageCheck.id.asc()).all()
    pilots = db.query(PilotHost).order_by(PilotHost.hostname.asc()).all()
    signoffs = db.query(AcceptanceSignOff).order_by(AcceptanceSignOff.signed_at.desc()).all()

    matrix = []
    for c in cases:
        matrix.append(
            {
                "case_id": c.case_id,
                "family": c.family,
                "title": c.title,
                "requirements": [x.strip() for x in (c.requirement_refs or "").split(",") if x.strip()],
                "status": c.status,
                "evidence": c.evidence,
                "tester": c.tester,
                "tested_at": c.tested_at.isoformat() if c.tested_at else None,
            }
        )

    return {
        "milestone": "M4 Lot 1",
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "coverage": cov,
        "uat": uat,
        "traceability_matrix": matrix,
        "des004_rows": [
            {
                "check_id": r.id,
                "plugin": r.plugin,
                "status": r.status,
                "verified_at": r.verified_at.isoformat() if r.verified_at else None,
                "decommissioned_at": r.decommissioned_at.isoformat() if r.decommissioned_at else None,
            }
            for r in checks
        ],
        "pilot_hosts": [
            {
                "id": p.id,
                "hostname": p.hostname,
                "agent_id": p.agent_id,
                "status": p.status,
            }
            for p in pilots
        ],
        "signoffs": [
            {
                "role": s.role,
                "name": s.name,
                "decision": s.decision,
                "comment": s.comment,
                "signed_at": s.signed_at.isoformat() if s.signed_at else None,
            }
            for s in signoffs
        ],
        "go_no_go": {
            "coverage_zero_open_musts": cov["zero_open_musts"],
            "uat_lot1_complete": uat["lot1_uat_complete"],
            "signoffs_present": len(signoffs) > 0,
            "ready_for_m4": cov["zero_open_musts"] and uat["lot1_uat_complete"] and len(signoffs) > 0,
        },
    }
