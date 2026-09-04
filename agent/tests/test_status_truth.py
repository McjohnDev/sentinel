"""L'etat rapporte par l'hote doit correspondre a la realite.

Le parc affichait « Hors ligne » pendant que `status` annoncait
« Liaison : etablie ». Les deux disaient vrai sur des questions
differentes — la derniere tentative avait reussi, mais plus rien ne battait
depuis — et c'est la confusion des deux qui trompait. Sur un produit de
supervision, un ecran qui affirme une liaison qui n'existe plus est pire
qu'un ecran vide.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from cli import _age_seconds, _humanise
from instance_lock import lock_file, running_pid


def _iso(delta_seconds: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(seconds=delta_seconds)).isoformat()


def test_no_lock_means_no_agent_running():
    assert running_pid() is None


def test_a_lock_held_by_this_process_is_reported():
    lock_file().parent.mkdir(parents=True, exist_ok=True)
    lock_file().write_text(str(os.getpid()), encoding="utf-8")
    assert running_pid() == os.getpid()


def test_a_lock_left_by_a_dead_process_is_not_a_running_agent():
    # Un verrou survit a un arret brutal. Le lire comme « un agent tourne »
    # ferait dire a l'hote exactement le contraire de la verite.
    lock_file().parent.mkdir(parents=True, exist_ok=True)
    lock_file().write_text("999999999", encoding="utf-8")
    assert running_pid() is None


def test_an_unreadable_lock_is_not_a_running_agent():
    lock_file().parent.mkdir(parents=True, exist_ok=True)
    lock_file().write_text("pas un pid", encoding="utf-8")
    assert running_pid() is None


def test_age_is_measured_from_the_timestamp():
    assert _age_seconds(_iso(0)) < 5
    assert 590 <= _age_seconds(_iso(600)) <= 610


def test_a_naive_timestamp_is_read_as_utc():
    naive = (datetime.now(timezone.utc) - timedelta(seconds=120)).replace(tzinfo=None)
    age = _age_seconds(naive.isoformat())
    assert age is not None and 110 <= age <= 130


def test_a_missing_or_broken_timestamp_does_not_crash():
    assert _age_seconds(None) is None
    assert _age_seconds("pas une date") is None


def test_the_age_is_shown_because_that_is_what_is_read():
    # « 2026-09-03T17:00:14 » ne dit rien a qui regarde ; « il y a 13 min »
    # repond directement a la question posee devant la machine.
    assert "il y a 30 s" in _humanise(_iso(30), 30)
    assert "il y a 13 min" in _humanise(_iso(800), 800)
    assert "il y a 2 h" in _humanise(_iso(7500), 7500)
    assert _humanise(None, None) == "jamais"
