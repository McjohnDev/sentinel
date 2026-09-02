"""Retire des hôtes de l'inventaire, avec tout ce qui en dépend.

Deux usages :

* remise à zéro complète du parc (point 0 du plan de reprise) ;
* retrait ciblé de quelques hôtes — un poste de démonstration, un doublon
  laissé par un essai.

**L'ordre de suppression n'est pas écrit en dur.** Il est déduit des clés
étrangères réellement déclarées dans la base. Une liste figée paraît marcher
jusqu'au jour où une table s'ajoute : la suppression échoue alors sur une
contrainte, à moitié appliquée, et personne n'a touché à ce script depuis des
mois. Elle échoue aussi en silence à l'inverse — une liste vérifiée sous
SQLite, qui n'applique pas les clés étrangères par défaut, passe tous les
tests et casse à la première exécution sur PostgreSQL.

Usage :
    python scripts/ops/purge_agents.py --dry-run
    python scripts/ops/purge_agents.py --only 5FADDF,02A1FE --yes
    python scripts/ops/purge_agents.py --yes            # tout le parc
"""

from __future__ import annotations

import argparse
import os
from typing import List, Optional, Sequence

# Aucun import du produit : ce script ne dépend que de SQLAlchemy, pour
# pouvoir être exécuté depuis n'importe où — un conteneur, un poste
# d'exploitation — sans transporter le dépôt avec lui.
from sqlalchemy import create_engine, inspect, text

#: Tables conservées quoi qu'il arrive. Effacer la trace de ce qui a été fait
#: au parc précédent n'est pas le but d'une remise à zéro d'inventaire, et un
#: audit bancaire doit y survivre.
PRESERVED = (
    "users", "admin_groups", "admin_group_members", "audit_logs",
    "global_settings", "messaging_config", "retention_config",
    "mail_templates", "ldap_role_mappings", "vlan_subnets",
)


def _referencing(inspector, target: str) -> List[str]:
    """Tables portant une clé étrangère vers `target`."""
    found = []
    for table in inspector.get_table_names():
        if table == target:
            continue
        for fk in inspector.get_foreign_keys(table):
            if fk.get("referred_table") == target:
                found.append(table)
                break
    return sorted(set(found))


def deletion_order(engine) -> List[str]:
    """Tables à vider, des feuilles vers la racine.

    `alerts` a ses propres dépendants (la chronologie) : ils passent d'abord,
    sinon la suppression bute sur `alert_events_alert_id_fkey`.
    """
    inspector = inspect(engine)
    existing = set(inspector.get_table_names())

    alert_children = [t for t in _referencing(inspector, "alerts") if t in existing]
    agent_children = [t for t in _referencing(inspector, "agents") if t in existing]

    order: List[str] = []
    for table in alert_children:
        if table not in order:
            order.append(table)
    if "alerts" in existing and "alerts" not in order:
        order.append("alerts")
    for table in agent_children:
        if table not in order and table not in PRESERVED:
            order.append(table)
    # `enrollment_tokens` ne référence pas les agents mais n'a plus d'objet
    # une fois le parc vidé — sauf en retrait ciblé, où d'autres hôtes
    # restent et peuvent encore s'enrôler.
    order.append("agents")
    return order


def _agent_filter(table: str, agent_ids: Optional[Sequence[str]]) -> str:
    if not agent_ids:
        return ""
    quoted = ", ".join("'%s'" % a.replace("'", "''") for a in agent_ids)
    column = "id" if table == "agents" else "agent_id"
    return " WHERE %s IN (%s)" % (column, quoted)


def _alert_scoped_filter(agent_ids: Optional[Sequence[str]]) -> str:
    """Pour les dépendants d'`alerts` qui ne portent pas d'`agent_id`."""
    if not agent_ids:
        return ""
    quoted = ", ".join("'%s'" % a.replace("'", "''") for a in agent_ids)
    return " WHERE alert_id IN (SELECT id FROM alerts WHERE agent_id IN (%s))" % quoted


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="compte sans effacer")
    parser.add_argument("--yes", action="store_true", help="confirme l'effacement")
    parser.add_argument(
        "--only",
        help="identifiants d'hôtes à retirer, séparés par des virgules. "
             "Sans cette option, tout le parc est vidé.",
    )
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    args = parser.parse_args()

    if not args.database_url:
        print("DATABASE_URL absent : passer --database-url ou renseigner l'environnement.")
        return 2
    if not args.dry_run and not args.yes:
        print("Refus : ajouter --yes pour executer, ou --dry-run pour compter.")
        return 2

    agent_ids = [a.strip() for a in args.only.split(",") if a.strip()] if args.only else None

    engine = create_engine(args.database_url)
    order = deletion_order(engine)
    inspector = inspect(engine)

    if agent_ids:
        print("Retrait cible : %s" % ", ".join(agent_ids))
    else:
        print("Remise a zero complete de l'inventaire.")
    print()

    total = 0
    with engine.begin() as cx:
        if agent_ids:
            known = cx.execute(
                text("SELECT id FROM agents WHERE id IN (%s)" % ", ".join("'%s'" % a for a in agent_ids))
            ).fetchall()
            missing = set(agent_ids) - {row[0] for row in known}
            if missing:
                # Nommer ce qui n'existe pas : un identifiant mal recopie
                # produirait sinon un « 0 ligne effacee » qu'on lit comme un
                # succes.
                print("Hotes inconnus, ignores : %s" % ", ".join(sorted(missing)))
                print()

        for table in order:
            columns = {c["name"] for c in inspector.get_columns(table)}
            if agent_ids and "agent_id" not in columns and table != "agents":
                where = _alert_scoped_filter(agent_ids)
            else:
                where = _agent_filter(table, agent_ids)

            try:
                count = cx.execute(text("SELECT COUNT(*) FROM %s%s" % (table, where))).scalar() or 0
            except Exception as exc:
                print("  %-26s ignoree (%s)" % (table, str(exc).splitlines()[0][:60]))
                continue

            total += count
            if args.dry_run:
                print("  %-26s %6d ligne(s) seraient effacees" % (table, count))
            elif count:
                cx.execute(text("DELETE FROM %s%s" % (table, where)))
                print("  %-26s %6d ligne(s) effacees" % (table, count))

    print()
    print("%d ligne(s) au total." % total)
    print("Conservees : %s" % ", ".join(PRESERVED))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
