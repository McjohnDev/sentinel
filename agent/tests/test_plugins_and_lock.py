"""Tests for agent instance lock and CPU plugin (FS1)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
AGENT_SRC = Path(__file__).resolve().parents[1] / "src"
for p in (str(ROOT), str(AGENT_SRC)):
    if p not in sys.path:
        sys.path.insert(0, p)

from instance_lock import InstanceLock, InstanceLockError  # noqa: E402
from plugins import build_default_registry  # noqa: E402


def test_instance_lock_blocks_a_live_foreign_instance(tmp_path, monkeypatch):
    """Un agent déjà lancé par un AUTRE processus doit bloquer le démarrage.

    La version précédente prenait deux verrous depuis le même processus et
    attendait un refus — ce que le contournement Docker interdit justement :
    un verrou portant *notre propre* PID est tenu pour périmé, sans quoi un
    conteneur redémarré (toujours PID 1) ne repartirait jamais. Les deux
    tests se contredisaient donc par construction, et celui-ci échouait en
    décrivant une situation qui ne peut pas se produire.

    Le vrai cas est ici : un PID étranger, et vivant.
    """
    lock_path = tmp_path / "cbc-agent-test.pid"
    foreign_pid = os.getpid() + 1
    lock_path.write_text(str(foreign_pid), encoding="utf-8")
    monkeypatch.setattr("instance_lock._pid_exists", lambda pid: pid == foreign_pid)

    lock = InstanceLock(name="cbc-agent-test", directory=str(tmp_path))
    with pytest.raises(InstanceLockError):
        lock.acquire()

    assert lock_path.read_text(encoding="utf-8").strip() == str(foreign_pid),         "le verrou d'un agent vivant ne doit pas être écrasé"


def test_instance_lock_reclaims_a_dead_holder(tmp_path, monkeypatch):
    """Un agent tué sans nettoyage ne doit pas condamner la machine."""
    lock_path = tmp_path / "cbc-agent-test.pid"
    lock_path.write_text("999999", encoding="utf-8")
    monkeypatch.setattr("instance_lock._pid_exists", lambda pid: False)

    lock = InstanceLock(name="cbc-agent-test", directory=str(tmp_path))
    lock.acquire()
    assert lock_path.read_text(encoding="utf-8").strip() == str(os.getpid())
    lock.release()


def test_lock_directory_can_be_moved_out_of_the_user_temp(tmp_path, monkeypatch):
    """Sous Windows, `%TEMP%` est propre à l'utilisateur.

    Deux comptes y détiendraient chacun un verrou « unique » sur la même
    machine. La variable permet de viser un répertoire commun à l'hôte.
    """
    monkeypatch.setenv(InstanceLock.LOCK_DIR_ENV, str(tmp_path))
    assert InstanceLock(name="cbc-agent-test").path.parent == tmp_path


def test_instance_lock_treats_own_pid_as_stale(tmp_path):
    """Docker restarts reuse PID 1; a leftover lock for our own PID is stale."""
    lock_path = tmp_path / "cbc-agent-stale.pid"
    lock_path.write_text(str(os.getpid()), encoding="utf-8")
    lock = InstanceLock(name="cbc-agent-stale")
    lock._path = lock_path
    lock.acquire()
    assert lock_path.read_text(encoding="utf-8").strip() == str(os.getpid())
    lock.release()


def test_cpu_plugin_emits_metric_v1():
    registry = build_default_registry()
    names = {m.name for m in registry.list_manifests()}
    assert {"cpu.collector", "memory.collector", "disk.collector", "network.collector", "process.collector"} <= names

    import uuid

    metrics = registry.collect_all(
        {"agent_id": str(uuid.uuid4()), "hostname": "test-host"}
    )
    families = {m.family for m in metrics}
    assert "cpu" in families
    assert "memory" in families
    assert "network" in families or "process" in families
    assert metrics[0].schema_name == "metric.v1"
