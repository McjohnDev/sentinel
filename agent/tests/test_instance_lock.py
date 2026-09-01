"""Un seul agent à la fois sur un hôte.

Deux `run` simultanés — le service installé plus un lancement à la main pour
diagnostiquer, le cas le plus courant — écrivent tous deux les mêmes fichiers
d'état. Le dernier qui écrit gagne, et l'agent peut alors acquitter une
version de plan que l'autre n'a jamais rangée.
"""

from __future__ import annotations

import os

import pytest

import instance_lock
from instance_lock import AlreadyRunning, InstanceLock, read_holder


def test_the_lock_records_its_holder():
    with InstanceLock():
        assert read_holder() == os.getpid()


def test_the_lock_is_released_on_exit():
    with InstanceLock():
        pass
    assert read_holder() is None


def test_a_second_instance_is_refused_and_names_the_culprit(monkeypatch):
    monkeypatch.setattr(instance_lock, "_process_alive", lambda _pid: True)
    instance_lock.lock_file().parent.mkdir(parents=True, exist_ok=True)
    instance_lock.lock_file().write_text("4242\n", encoding="utf-8")

    with pytest.raises(AlreadyRunning) as exc:
        InstanceLock().acquire()

    # Nommer le processus fautif : « conflit » sans coupable n'aide personne.
    assert "4242" in str(exc.value)


def test_a_stale_lock_from_a_dead_process_is_reclaimed(monkeypatch):
    # Refuser de démarrer après un arrêt brutal serait pire que le risque
    # qu'on cherche à écarter.
    monkeypatch.setattr(instance_lock, "_process_alive", lambda _pid: False)
    instance_lock.lock_file().parent.mkdir(parents=True, exist_ok=True)
    instance_lock.lock_file().write_text("999999\n", encoding="utf-8")

    with InstanceLock():
        assert read_holder() == os.getpid()


def test_an_unreadable_lock_does_not_block_startup():
    instance_lock.lock_file().parent.mkdir(parents=True, exist_ok=True)
    instance_lock.lock_file().write_text("ceci n'est pas un PID", encoding="utf-8")

    with InstanceLock():
        assert read_holder() == os.getpid()


def test_the_same_process_may_re_acquire():
    # Un agent qui relance sa boucle ne doit pas se bloquer lui-même.
    first = InstanceLock().acquire()
    second = InstanceLock().acquire()
    assert read_holder() == os.getpid()
    second.release()
    first.release()


def test_releasing_a_lock_taken_over_by_another_leaves_it_alone(monkeypatch):
    lock = InstanceLock().acquire()
    # Entre-temps un autre agent a légitimement repris la place.
    instance_lock.lock_file().write_text("4242\n", encoding="utf-8")

    lock.release()

    assert read_holder() == 4242, "on n'efface que son propre verrou"


def test_a_missing_lock_file_reads_as_free():
    assert read_holder() is None


def test_process_liveness_answers_true_when_in_doubt():
    # Se tromper dans ce sens fait échouer un démarrage avec un message
    # clair ; se tromper dans l'autre laisse deux agents tourner.
    assert instance_lock._process_alive(os.getpid()) is True
    assert instance_lock._process_alive(0) is False
    assert instance_lock._process_alive(-1) is False
