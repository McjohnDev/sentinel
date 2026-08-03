"""add_indexes_for_performance

Revision ID: c237583e7562
Revises: 2c19bcc02e6d
Create Date: 2026-08-03 04:44:05.163089

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c237583e7562'
down_revision: Union[str, None] = '2c19bcc02e6d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Index sur les agents pour les requêtes fréquentes
    op.create_index('idx_agents_status', 'agents', ['status'])
    op.create_index('idx_agents_last_communication', 'agents', ['last_communication'])
    op.create_index('idx_agents_machine_id', 'agents', ['machine_id'], unique=True)
    
    # Index sur les heartbeats pour l'historique
    op.create_index('idx_heartbeats_agent_id', 'heartbeats', ['agent_id'])
    op.create_index('idx_heartbeats_timestamp', 'heartbeats', ['timestamp'])
    op.create_index('idx_heartbeats_agent_timestamp', 'heartbeats', ['agent_id', 'timestamp'])
    
    # Index sur les alertes pour le filtrage
    op.create_index('idx_alerts_status', 'alerts', ['status'])
    op.create_index('idx_alerts_severity', 'alerts', ['severity'])
    op.create_index('idx_alerts_agent_id', 'alerts', ['agent_id'])
    op.create_index('idx_alerts_started_at', 'alerts', ['started_at'])
    op.create_index('idx_alerts_status_started', 'alerts', ['status', 'started_at'])


def downgrade() -> None:
    # Suppression des indexes
    op.drop_index('idx_alerts_status_started', table_name='alerts')
    op.drop_index('idx_alerts_started_at', table_name='alerts')
    op.drop_index('idx_alerts_agent_id', table_name='alerts')
    op.drop_index('idx_alerts_severity', table_name='alerts')
    op.drop_index('idx_alerts_status', table_name='alerts')
    
    op.drop_index('idx_heartbeats_agent_timestamp', table_name='heartbeats')
    op.drop_index('idx_heartbeats_timestamp', table_name='heartbeats')
    op.drop_index('idx_heartbeats_agent_id', table_name='heartbeats')
    
    op.drop_index('idx_agents_machine_id', table_name='agents')
    op.drop_index('idx_agents_last_communication', table_name='agents')
    op.drop_index('idx_agents_status', table_name='agents')
