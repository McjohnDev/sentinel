"""Additive schema patches for existing Postgres volumes (create_all does not ALTER)."""

from __future__ import annotations

import logging

from sqlalchemy import text

logger = logging.getLogger(__name__)

_COLUMNS = [
    ("global_settings", "threshold_duration_seconds", "INTEGER DEFAULT 300"),
    ("global_settings", "escalate_after_minutes", "INTEGER DEFAULT 15"),
    ("global_settings", "alert_reminder_hours", "REAL DEFAULT 3"),
    ("global_settings", "agent_cpu_max_percent", "REAL DEFAULT 2"),
    ("global_settings", "agent_ram_max_mb", "REAL DEFAULT 300"),
    ("alerts", "mail_status", "VARCHAR"),
    ("alerts", "webhook_status", "VARCHAR"),
    ("alerts", "escalated_at", "TIMESTAMP"),
    ("alerts", "verdict", "VARCHAR"),
    ("alerts", "assigned_to", "VARCHAR"),
    ("alerts", "assigned_at", "TIMESTAMP"),
    ("alerts", "assigned_by", "VARCHAR"),
    ("alerts", "resolved_by", "VARCHAR"),
    ("alerts", "reminder_hours", "REAL"),
    ("alerts", "last_reminder_at", "TIMESTAMP"),
    ("alerts", "reminder_count", "INTEGER DEFAULT 0"),
    ("messaging_config", "webhook_url", "VARCHAR"),
    ("messaging_config", "webhook_secret", "VARCHAR"),
    ("messaging_config", "webhook_enabled", "BOOLEAN DEFAULT FALSE"),
    ("messaging_config", "smtp_enabled", "BOOLEAN DEFAULT FALSE"),
    ("messaging_config", "smtp_host", "VARCHAR"),
    ("messaging_config", "smtp_port", "INTEGER DEFAULT 25"),
    ("messaging_config", "smtp_auth", "BOOLEAN DEFAULT FALSE"),
    ("messaging_config", "smtp_username", "VARCHAR"),
    ("messaging_config", "smtp_password", "VARCHAR"),
    ("messaging_config", "smtp_encryption", "VARCHAR DEFAULT 'none'"),
    ("messaging_config", "smtp_from", "VARCHAR"),
    ("messaging_config", "smtp_from_name", "VARCHAR"),
    ("messaging_config", "smtp_verify_cert", "BOOLEAN DEFAULT TRUE"),
    ("agents", "group_id", "VARCHAR"),
    ("agents", "config_version_acked", "INTEGER DEFAULT 0"),
    ("agents", "agent_cpu_percent", "REAL"),
    ("agents", "agent_ram_mb", "REAL"),
    ("agents", "capability_level", "VARCHAR DEFAULT 'L0'"),
    ("alerts", "mount", "VARCHAR"),
    ("heartbeats", "disk_mount", "VARCHAR"),
    ("heartbeats", "disks_json", "VARCHAR"),
    ("global_settings", "disk_mount_rules", "TEXT DEFAULT '[]'"),
    ("agents", "disk_mount_rules", "TEXT"),
    ("agents", "owner_user_id", "VARCHAR"),
    ("users", "manager_id", "VARCHAR"),
    # API-003 / DSH-025 — provenance du compte et traçabilité des connexions.
    ("users", "auth_source", "VARCHAR DEFAULT 'LOCAL'"),
    ("users", "external_id", "VARCHAR"),
    ("users", "last_login_at", "TIMESTAMP"),
    # AGT-002 / point 2 — caractéristiques d'hôte constatées par l'agent.
    ("agents", "cpu_cores", "INTEGER"),
    ("agents", "ram_total_gb", "REAL"),
    ("agents", "disk_total_gb", "REAL"),
    # Segmentation réseau : VLAN constaté par l'hôte, VLAN déclaré par
    # l'exploitation. Deux champs parce que la plupart des hôtes ne peuvent
    # pas connaître leur VLAN — voir models.Agent.
    ("vlan_subnets", "range_start", "VARCHAR"),
    ("vlan_subnets", "range_end", "VARCHAR"),
    ("global_settings", "heartbeat_interval_seconds", "INTEGER DEFAULT 30"),
    ("agents", "heartbeat_interval_seconds", "INTEGER"),
    ("agents", "inventory_json", "TEXT"),
    ("agents", "inventory_at", "TIMESTAMP"),
    ("agents", "vlan_observed", "VARCHAR"),
    ("agents", "vlan", "VARCHAR"),
    # AGT-012 / point 9 — comment et où l'agent s'exécute sur l'hôte.
    ("agents", "runtime_json", "TEXT"),
    ("agents", "run_mode", "VARCHAR"),
    ("agents", "run_as_user", "VARCHAR"),
    # Point 4 — désinstallation tracée plutôt que ligne effacée.
    ("agents", "uninstalled_at", "TIMESTAMP"),
    ("agents", "uninstalled_by", "VARCHAR"),
    # Point 3 — équipe responsable de l'hôte.
    ("agents", "admin_group_id", "VARCHAR"),
    # Point 6 — plan de supervision par hôte.
    ("agents", "monitoring_version", "INTEGER DEFAULT 0"),
    ("agents", "monitoring_version_acked", "INTEGER DEFAULT 0"),
    ("alerts", "target", "VARCHAR"),
]


def ensure_schema(engine) -> None:
    dialect = engine.dialect.name
    if dialect == "postgresql":
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            # Column(SQLEnum(AlertSeverity)) sans values_callable : SQLAlchemy
            # persiste le NOM du membre ("MINOR"), pas sa valeur ("minor").
            # Sur un volume Postgres créé avant l'ajout de MINOR/MAJOR, insérer
            # une alerte de ces gravités échouait et faisait tomber le
            # heartbeat en 500. On backfill les deux casses, comme alerttype.
            for val in ("minor", "major", "MINOR", "MAJOR", "info", "INFO", "critical", "CRITICAL"):
                conn.execute(text(f"ALTER TYPE alertseverity ADD VALUE IF NOT EXISTS '{val}'"))
            # Nouveau rôle sécurité (DSH-025). Même précaution de casse que
            # ci-dessus : SQLAlchemy persiste le NOM du membre.
            for val in ("security", "SECURITY"):
                conn.execute(text(f"ALTER TYPE userrole ADD VALUE IF NOT EXISTS '{val}'"))
            for val in (
                "log_pattern",
                "rate_limit",
                "agent_footprint",
                "LOG_PATTERN",
                "RATE_LIMIT",
                "AGENT_FOOTPRINT",
            ):
                conn.execute(text(f"ALTER TYPE alerttype ADD VALUE IF NOT EXISTS '{val}'"))
    with engine.begin() as conn:
        for table, col, typ in _COLUMNS:
            try:
                if dialect == "sqlite":
                    rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
                    names = {r[1] for r in rows}
                    if col not in names:
                        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {typ}"))
                else:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {typ}"))
            except Exception:
                logger.debug("schema patch skipped %s.%s", table, col, exc_info=True)
