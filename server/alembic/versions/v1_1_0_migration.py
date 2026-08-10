"""v1_1_0_migration

Revision ID: v1_1_0
Revises: 997a40cffb7f
Create Date: 2026-08-08 09:36:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'v1_1_0'
down_revision: Union[str, None] = '997a40cffb7f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # === EXIGENCE 4: Ajout de machine_type dans la table agents ===
    # Créer l'ENUM pour machine_type
    machine_type_enum = postgresql.ENUM('server', 'workstation', name='machinetype')
    machine_type_enum.create(op.get_bind())
    
    # Ajouter la colonne machine_type avec une valeur par défaut
    op.add_column('agents', sa.Column('machine_type', sa.Enum('server', 'workstation', name='machinetype'), nullable=False, server_default='workstation'))
    
    # === SUPPRESSION DES 3 TÉLÉMÉTRIES de la table heartbeats ===
    op.drop_column('heartbeats', 'cpu_architecture')
    op.drop_column('heartbeats', 'latency_ms')
    op.drop_column('heartbeats', 'temperature_celsius')
    
    # === EXIGENCE 2: Remplacement de email_config par messaging_config ===
    # Créer la nouvelle table messaging_config
    op.create_table(
        'messaging_config',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('recipients', sa.String(), default='[]'),
        sa.Column('api_endpoint', sa.String()),
        sa.Column('api_key', sa.String()),
        sa.Column('api_timeout', sa.Integer(), default=30),
        sa.Column('enabled', sa.Boolean(), default=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now())
    )
    
    # Insérer la configuration par défaut
    op.execute("INSERT INTO messaging_config (id, recipients, api_endpoint, api_key, api_timeout, enabled) VALUES ('default', '[]', NULL, NULL, 30, True)")
    
    # Supprimer l'ancienne table email_config
    op.drop_table('email_config')
    
    # === EXIGENCE 3: Création de la table notification_channel_status ===
    op.create_table(
        'notification_channel_status',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('status', sa.String(), default='unknown'),
        sa.Column('last_check', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('last_success', sa.DateTime(), nullable=True),
        sa.Column('last_error', sa.DateTime(), nullable=True),
        sa.Column('error_message', sa.String(), nullable=True),
        sa.Column('consecutive_failures', sa.Integer(), default=0),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now())
    )
    
    # Insérer le statut par défaut
    op.execute("INSERT INTO notification_channel_status (id, status) VALUES ('default', 'unknown')")
    
    # === EXIGENCE 1: Création des tables pour supervision services et fichiers ===
    op.create_table(
        'service_monitoring',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('agent_id', sa.String(), sa.ForeignKey('agents.id'), nullable=False, index=True),
        sa.Column('service_name', sa.String(), nullable=False, index=True),
        sa.Column('status', sa.String(), default='unknown'),
        sa.Column('last_check', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now())
    )
    
    op.create_table(
        'file_monitoring',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('agent_id', sa.String(), sa.ForeignKey('agents.id'), nullable=False, index=True),
        sa.Column('file_path', sa.String(), nullable=False, index=True),
        sa.Column('exists', sa.Boolean(), default=False),
        sa.Column('size_bytes', sa.Integer(), nullable=True),
        sa.Column('last_modified', sa.DateTime(), nullable=True),
        sa.Column('last_check', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now())
    )


def downgrade() -> None:
    # === Rollback de la table file_monitoring ===
    op.drop_table('file_monitoring')
    
    # === Rollback de la table service_monitoring ===
    op.drop_table('service_monitoring')
    
    # === Rollback de notification_channel_status ===
    op.drop_table('notification_channel_status')
    
    # === Rollback de messaging_config vers email_config ===
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
    
    op.execute("INSERT INTO email_config (id, recipients, smtp_host, smtp_port, smtp_secure, smtp_user) VALUES ('default', '[]', NULL, 587, True, NULL)")
    
    op.drop_table('messaging_config')
    
    # === Réajout des 3 télémétries dans heartbeats ===
    op.add_column('heartbeats', sa.Column('temperature_celsius', sa.Float(), nullable=True))
    op.add_column('heartbeats', sa.Column('latency_ms', sa.Float()))
    op.add_column('heartbeats', sa.Column('cpu_architecture', sa.String()))
    
    # === Suppression de machine_type de agents ===
    op.drop_column('agents', 'machine_type')
    
    # Supprimer l'ENUM machine_type
    machine_type_enum = postgresql.ENUM('server', 'workstation', name='machinetype')
    machine_type_enum.drop(op.get_bind())
