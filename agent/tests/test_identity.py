"""Identité stable de la machine.

L'enjeu tient en une phrase : si l'identité change entre deux démarrages, la
plateforme crée un second hôte pour la même machine et l'historique se scinde.
"""

from __future__ import annotations

from identity import is_valid_machine_id, load_or_create_machine_id, read_machine_id


def test_identity_survives_a_restart():
    first = load_or_create_machine_id()
    second = load_or_create_machine_id()
    assert first == second


def test_identity_is_acceptable_to_the_platform():
    # La plateforme valide `^[a-zA-Z0-9\-_]+$` sur machine_id : une identité
    # que l'agent tire lui-même mais que l'API refuse rendrait l'enrôlement
    # impossible sans message compréhensible.
    assert is_valid_machine_id(load_or_create_machine_id())


def test_a_corrupted_identity_is_not_reused(isolated_state):
    path = isolated_state / "machine_id"
    path.write_text("pas une identité valide !!\n", encoding="utf-8")

    assert read_machine_id(path) is None

    regenerated = load_or_create_machine_id(path)
    assert is_valid_machine_id(regenerated)


def test_surrounding_whitespace_is_tolerated(isolated_state):
    path = isolated_state / "machine_id"
    path.write_text("  550e8400-e29b-41d4-a716-446655440000  \n", encoding="utf-8")
    assert read_machine_id(path) == "550e8400-e29b-41d4-a716-446655440000"


def test_missing_file_is_not_an_error(isolated_state):
    assert read_machine_id(isolated_state / "absent") is None
