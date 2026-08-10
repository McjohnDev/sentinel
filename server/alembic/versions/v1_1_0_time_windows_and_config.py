"""Ajout des modèles de configuration pour fenêtres horaires et supervision

Revision ID: v1_1_0_time_windows
Revises: v1_1_0_migration
Create Date: 2025-01-09

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'v1_1_0_time_windows'
down_revision = 'v1_1_0_migration'
branch_labels = None
depends_on = None


def upgrade():
    # Création de la table availability_policies
    op.create_table(
        'availability_policies',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('agent_id', sa.String(), nullable=True),
        sa.Column('time_windows', sa.String(), nullable=True, server_default='{}'),
        sa.Column('offline_threshold_seconds', sa.Integer(), nullable=True),
        sa.Column('time_windows_enabled', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=True, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_availability_policies_agent_id'), 'availability_policies', ['agent_id'], unique=False)
    
    # Création de la table service_monitoring_config
    op.create_table(
        'service_monitoring_config',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('agent_id', sa.String(), nullable=True),
        sa.Column('service_name', sa.String(), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('expected_status', sa.String(), nullable=True, server_default='running'),
        sa.Column('check_interval_seconds', sa.Integer(), nullable=True, server_default='60'),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=True, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_service_monitoring_config_agent_id'), 'service_monitoring_config', ['agent_id'], unique=False)
    op.create_index(op.f('ix_service_monitoring_config_service_name'), 'service_monitoring_config', ['service_name'], unique=False)
    
    # Création de la table file_monitoring_config
    op.create_table(
        'file_monitoring_config',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('agent_id', sa.String(), nullable=True),
        sa.Column('file_path', sa.String(), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('max_size_mb', sa.Integer(), nullable=True),
        sa.Column('check_interval_seconds', sa.Integer(), nullable=True, server_default='300'),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=True, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_file_monitoring_config_agent_id'), 'file_monitoring_config', ['agent_id'], unique=False)
    op.create_index(op.f('ix_file_monitoring_config_file_path'), 'file_monitoring_config', ['file_path'], unique=False)
    
    # Création de la politique de disponibilité par défaut
    op.execute("""
        INSERT INTO availability_policies (id, time_windows_enabled, time_windows)
        VALUES ('default', false, '{}')
    """)


def downgrade():
    # Suppression des tables
    op.drop_index(op.f('ix_file_monitoring_config_file_path'), table_name='file_monitoring_config')
    op.drop_index(op.f('ix_file_monitoring_config_agent_id'), table_name='file_monitoring_config')
    op.drop_table('file_monitoring_config')
    
    op.drop_index(op.f('ix_service_monitoring_config_service_name'), table_name='service_monitoring_config')
    op.drop_index(op.f('ix_service_monitoring_config_agent_id'), table_name='service_monitoring_config')
    op.drop_table('service_monitoring_config')
    
    op.drop_index(op.f('ix_availability_policies_agent_id'), table_name='availability_policies')
    op.drop_table('availability_policies')
