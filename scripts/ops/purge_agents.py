"""Vide l'inventaire d'agents de la plateforme.

Point 0 du plan de reprise : repartir d'un parc vide pour rejouer
l'enrolement (point 1) sur des hotes propres.

Ne touche ni aux comptes utilisateurs, ni aux groupes d'administration, ni
aux reglages globaux, ni au journal d'audit : effacer la trace de ce qui a
ete fait au parc precedent n'est pas le but, et un audit bancaire doit
survivre a une remise a zero d'inventaire.

Usage :
    python scripts/ops/purge_agents.py --dry-run     # compte, n'ecrit rien
    python scripts/ops/purge_agents.py --yes         # execute

La base visee est celle de DATABASE_URL (voir server/.env).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT), str(ROOT / "server")):
    if p not in sys.path:
        sys.path.insert(0, p)

from sqlalchemy import create_engine, text  # noqa: E402

#: Ordre impose par les cles etrangeres : les enfants avant les parents.
TABLES = [
    "alert_events",
    "alerts",
    "heartbeats",
    "monitored_services",
    "monitored_files",
    "service_monitoring",
    "file_monitoring",
    "availability_policies",
    "remote_tasks",
    "action_approvals",
    "coverage_overlaps",
    "pilot_hosts",
    "enrollment_tokens",
    "agents",
]

#: Explicitement conservees, pour que l'intention soit lisible en revue.
PRESERVED = [
    "users",
    "admin_groups",
    "admin_group_members",
    "audit_logs",
    "global_settings",
    "messaging_config",
    "retention_config",
    "mail_templates",
    "ldap_role_mappings",
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="compte sans effacer")
    parser.add_argument("--yes", action="store_true", help="confirme l'effacement")
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    args = parser.parse_args()

    if not args.database_url:
        print("DATABASE_URL absent : passer --database-url ou renseigner l'environnement.")
        return 2
    if not args.dry_run and not args.yes:
        print("Refus : ajouter --yes pour executer, ou --dry-run pour compter.")
        return 2

    engine = create_engine(args.database_url)
    total = 0
    with engine.begin() as cx:
        for table in TABLES:
            try:
                count = cx.execute(text("SELECT COUNT(*) FROM %s" % table)).scalar() or 0
            except Exception:
                print("  %-24s absente — ignoree" % table)
                continue
            total += count
            if args.dry_run:
                print("  %-24s %6d ligne(s) seraient effacees" % (table, count))
            else:
                cx.execute(text("DELETE FROM %s" % table))
                print("  %-24s %6d ligne(s) effacees" % (table, count))

    print()
    print("%d ligne(s) au total." % total)
    print("Conservees : %s" % ", ".join(PRESERVED))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
