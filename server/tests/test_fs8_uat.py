"""FS8 — coverage transitions + acceptance pack helpers."""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

ROOT = Path(__file__).resolve().parents[2]
SERVER = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(SERVER)):
    if p not in sys.path:
        sys.path.insert(0, p)

from src.database import Base, SessionLocal, engine  # noqa: E402
from src.models import CoverageCheck  # noqa: E402
from src.uat_service import (  # noqa: E402
    apply_coverage_status,
    build_acceptance_pack,
    can_transition,
    ensure_coverage_seed,
    ensure_uat_seed,
)


def setup_module():
    Base.metadata.create_all(bind=engine)


def test_transition_rules():
    assert can_transition("delivered", "verified_in_production")
    assert can_transition("verified_in_production", "script_decommissioned")
    assert not can_transition("delivered", "script_decommissioned")
    assert can_transition("planned", "waived")


def test_seed_and_extinction_path():
    db = SessionLocal()
    try:
        ensure_coverage_seed(db)
        ensure_uat_seed(db)
        row = db.query(CoverageCheck).filter(CoverageCheck.id == "PS-001").first()
        assert row is not None
        assert row.status == "delivered"
        apply_coverage_status(row, "verified_in_production")
        apply_coverage_status(row, "script_decommissioned")
        db.commit()
        pack = build_acceptance_pack(db)
        assert pack["coverage"]["total"] >= 8
        assert "traceability_matrix" in pack
        assert "go_no_go" in pack
    finally:
        db.close()
