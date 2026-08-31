"""Identifiant d'agent : format court, attribué et vérifié par la plateforme.

L'UUID v4 précédent était exact mais inexploitable par un humain : 36
caractères qu'on ne peut ni dicter, ni retenir, ni comparer d'un coup d'œil
dans une liste. Le code hexadécimal à 6 caractères assume l'échange inverse —
lisible, mais dans un espace assez petit pour que l'unicité doive être
vérifiée plutôt que supposée.
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[2]
SERVER = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(SERVER)):
    if p not in sys.path:
        sys.path.insert(0, p)

from src.agent_identity import (  # noqa: E402
    AGENT_ID_LENGTH,
    AgentIdExhaustedError,
    generate_agent_id,
    is_valid_agent_id,
    normalize_agent_id,
)
from src.database import Base  # noqa: E402
from src.models import Agent, MachineType  # noqa: E402


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def _agent(db, agent_id: str):
    agent = Agent(
        id=agent_id,
        machine_id=f"mid-{uuid.uuid4().hex[:8]}",
        hostname=f"host-{agent_id}",
        auth_key=str(uuid.uuid4()),
        status="active",
        os="linux",
        machine_type=MachineType.SERVER,
    )
    db.add(agent)
    db.commit()
    return agent


# ------------------------------------------------------------------- format


def test_generated_id_has_the_documented_shape(db):
    generated = generate_agent_id(db)
    assert len(generated) == AGENT_ID_LENGTH == 6
    assert generated == generated.upper()
    assert all(c in "0123456789ABCDEF" for c in generated)
    assert is_valid_agent_id(generated)


@pytest.mark.parametrize(
    "value",
    ["", None, "A3F09", "A3F09C2", "a3f09c", "GHIJKL", "A3-F09", "550e8400-e29b"],
)
def test_malformed_identifiers_are_rejected(value):
    """Un identifiant hors format doit être écarté avant toute requête."""
    assert is_valid_agent_id(value) is False


def test_operator_typed_lowercase_is_accepted(db):
    """Recopier « a3f09c » depuis un ticket doit trouver le bon hôte."""
    assert normalize_agent_id("a3f09c") == "A3F09C"
    assert normalize_agent_id("  A3F09C  ") == "A3F09C"
    assert normalize_agent_id("pas-un-code") is None
    assert normalize_agent_id(None) is None


# ------------------------------------------------------------------ unicité


def test_generation_avoids_an_identifier_already_taken(db, monkeypatch):
    """La collision est rare mais doit coûter un tirage, pas une erreur 500.

    Sur 16,7 millions de combinaisons elle finira par arriver ; si elle
    remontait en 500, ce serait pendant un enrôlement — c'est-à-dire pendant
    l'installation d'un poste, au pire moment pour un incident inexpliqué.
    """
    _agent(db, "AAAAAA")

    draws = iter(["AAAAAA", "AAAAAA", "BBBBBB"])
    monkeypatch.setattr("src.agent_identity._draw", lambda: next(draws))

    assert generate_agent_id(db) == "BBBBBB"


def test_generation_gives_up_loudly_when_space_is_saturated(db, monkeypatch):
    """Saturation : erreur explicite plutôt que boucle ou doublon silencieux."""
    _agent(db, "AAAAAA")
    monkeypatch.setattr("src.agent_identity._draw", lambda: "AAAAAA")

    with pytest.raises(AgentIdExhaustedError):
        generate_agent_id(db)


def test_successive_identifiers_are_distinct(db):
    seen = set()
    for _ in range(50):
        generated = generate_agent_id(db)
        assert generated not in seen
        seen.add(generated)
        _agent(db, generated)
    assert len(seen) == 50
