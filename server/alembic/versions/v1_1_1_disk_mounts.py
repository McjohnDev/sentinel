"""Per-mount disk alerts and heartbeat disks_json.

Revision ID: v1_1_1_disk_mounts
Revises: v1_1_0_time_windows
Create Date: 2026-08-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "v1_1_1_disk_mounts"
down_revision: Union[str, None] = "v1_1_0_time_windows"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("heartbeats", sa.Column("disk_mount", sa.String(), nullable=True))
    op.add_column("heartbeats", sa.Column("disks_json", sa.String(), nullable=True))
    op.add_column("alerts", sa.Column("mount", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("alerts", "mount")
    op.drop_column("heartbeats", "disks_json")
    op.drop_column("heartbeats", "disk_mount")
