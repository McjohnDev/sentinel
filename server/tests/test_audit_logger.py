"""Journal d'audit — surface d'API et robustesse.

Régression couverte : `main.py` appelait `audit_logger.log_action(...)` sur 16
endpoints alors que la méthode n'existait pas. Chaque appel levait un
AttributeError *après* le `db.commit()` de l'endpoint : l'écriture était
persistée et le client recevait une HTTP 500, sans aucune trace d'audit.
"""

from __future__ import annotations

import io
import os
import re
import sys
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

ROOT = Path(__file__).resolve().parents[2]
SERVER = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(SERVER)):
    if p not in sys.path:
        sys.path.insert(0, p)

import pytest

from src.audit_logger import AuditLogger

MAIN_PY = SERVER / "src" / "main.py"


@pytest.fixture
def audit():
    return AuditLogger()


def test_every_audit_method_called_by_main_exists(audit):
    """Garde-fou : aucun endpoint ne doit appeler une méthode inexistante.

    C'est exactement la classe de bug corrigée ici, et elle est invisible
    jusqu'à ce qu'un opérateur atteigne l'endpoint en production.
    """
    source = io.open(MAIN_PY, encoding="utf-8").read()
    called = set(re.findall(r"audit_logger\.(\w+)\(", source))
    assert called, "aucun appel d'audit détecté — le motif de recherche a dû changer"

    missing = sorted(name for name in called if not hasattr(audit, name))
    assert not missing, f"méthodes d'audit appelées mais absentes : {missing}"


def test_log_action_accepts_the_call_shapes_used_in_main(audit):
    # Forme longue (ex. PURGE_LAB_AGENTS)
    audit.log_action(user_id="u1", action="PURGE_LAB_AGENTS", details="Deleted 3 agents")
    # Forme courte sur une ligne (ex. CREATE_GROUP)
    audit.log_action(user_id="u1", action="CREATE_GROUP", details="Agence")
    # Détail structuré
    audit.log_action(user_id="u1", action="ASSIGN_GROUP", details={"agent": "a1"})
    # Sans détail ni utilisateur
    audit.log_action(action="ANONYMOUS_ACTION")


def test_logging_failure_never_propagates(audit, monkeypatch):
    """Un échec de journalisation ne doit pas transformer une écriture
    déjà validée en réponse 500."""

    def boom(*_args, **_kwargs):
        raise OSError("disque plein")

    monkeypatch.setattr(audit.logger, "info", boom)
    # Ne doit pas lever.
    audit.log_action(user_id="u1", action="CREATE_GROUP", details="Agence")
    audit.log_event(event_type="TEST")


def test_non_serialisable_details_do_not_raise(audit):
    """`json.dumps` doit tolérer un objet arbitraire (default=str)."""

    class Opaque:
        pass

    audit.log_action(user_id="u1", action="X", details={"obj": Opaque()})
