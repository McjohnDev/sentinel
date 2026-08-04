"""add_settings_models_and_agent_fields

Revision ID: 997a40cffb7f
Revises: c237583e7562
Create Date: 2026-08-04 07:34:37.611008

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '997a40cffb7f'
down_revision: Union[str, None] = 'c237583e7562'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add name and location columns to agents table
    op.add_column('agents', sa.Column('name', sa.String(), nullable=True))
    op.add_column('agents', sa.Column('location', sa.String(), nullable=True))

    # Create global_settings table
    op.create_table(
        'global_settings',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('cpu_warning_threshold', sa.Float(), default=80),
        sa.Column('cpu_critical_threshold', sa.Float(), default=90),
        sa.Column('ram_warning_threshold', sa.Float(), default=80),
        sa.Column('ram_critical_threshold', sa.Float(), default=90),
        sa.Column('disk_warning_threshold', sa.Float(), default=85),
        sa.Column('disk_critical_threshold', sa.Float(), default=95),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now())
    )

    # Create email_config table
    op.create_table(
        'email_config',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('recipients', sa.String(), default='[]'),
        sa.Column('smtp_host', sa.String()),
        sa.Column('smtp_port', sa.Integer(), default=587),
        sa.Column('smtp_secure', sa.Boolean(), default=True),
        sa.Column('smtp_user', sa.String()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now())
    )

    # Create retention_config table
    op.create_table(
        'retention_config',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('alerts_days', sa.Integer(), default=30),
        sa.Column('heartbeats_days', sa.Integer(), default=7),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now())
    )

    # Create enrollment_tokens table
    op.create_table(
        'enrollment_tokens',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('token', sa.String(), unique=True, nullable=False, index=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('status', sa.String(), default='active'),
        sa.Column('created_by', sa.String())
    )

    # Insert default settings
    op.execute("INSERT INTO global_settings (id, cpu_warning_threshold, cpu_critical_threshold, ram_warning_threshold, ram_critical_threshold, disk_warning_threshold, disk_critical_threshold) VALUES ('default', 80, 90, 80, 90, 85, 95)")
    op.execute("INSERT INTO email_config (id, recipients, smtp_host, smtp_port, smtp_secure, smtp_user) VALUES ('default', '[]', NULL, 587, True, NULL)")
    op.execute("INSERT INTO retention_config (id, alerts_days, heartbeats_days) VALUES ('default', 30, 7)")


def downgrade() -> None:
    # Drop new tables
    op.drop_table('enrollment_tokens')
    op.drop_table('retention_config')
    op.drop_table('email_config')
    op.drop_table('global_settings')

    # Remove columns from agents table
    op.drop_column('agents', 'location')
    op.drop_column('agents', 'name')
