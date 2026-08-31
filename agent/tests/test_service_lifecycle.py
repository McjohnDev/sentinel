"""Arrêt propre de la boucle de supervision, prérequis du mode service.

Un service Windows doit se terminer dans le délai que lui laisse le
gestionnaire de services. `run()` était une boucle `while True` avec des
`time.sleep(1)` bloquants : on ne pouvait l'interrompre qu'en tuant le
processus. Windows aurait alors signalé un échec d'arrêt, et le tampon en
cours d'écriture aurait pu être tronqué.

Les mêmes garanties servent au mode console : Ctrl+C ou `agent-stop.ps1`
laissent l'agent finir son tour de boucle plutôt que de le trancher.
"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
AGENT_SRC = Path(__file__).resolve().parents[1] / "src"
for p in (str(ROOT), str(AGENT_SRC)):
    if p not in sys.path:
        sys.path.insert(0, p)

from agent import CBCAgent  # noqa: E402
from agent_paths import resolve_buffer_dir  # noqa: E402


@pytest.fixture
def offline_agent(tmp_path, monkeypatch):
    """Agent visant une plateforme injoignable, isolé du poste.

    L'injoignabilité est délibérée : elle place l'agent dans sa boucle de
    reconnexion, c'est-à-dire le cas où un arrêt est le plus susceptible de
    rester bloqué.
    """
    from instance_lock import InstanceLock

    monkeypatch.setenv(InstanceLock.LOCK_DIR_ENV, str(tmp_path))
    monkeypatch.setenv("AGENT_MACHINE_ID_FILE", str(tmp_path / "machine_id"))

    config = {
        # Port fermé : aucune connexion possible, donc reconnexion permanente.
        "server": {"url": "http://127.0.0.1:9", "enrollment_token": "x" * 12, "tls_verify": False},
        "agent": {"heartbeat_interval": 30, "ping_interval": 10, "machine_type": "workstation"},
        "degraded_mode": {"enabled": True, "buffer_dir": str(tmp_path / "buffer")},
        "logs": {"enabled": False},
        "services_monitoring": {"enabled": False},
        "files_monitoring": {"enabled": False},
        "logging": {"level": "CRITICAL", "file": str(tmp_path / "agent.log")},
    }
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    return CBCAgent(config_path=str(path))


def test_run_stops_when_asked(offline_agent):
    """La boucle doit rendre la main, pas se faire tuer."""
    thread = threading.Thread(target=offline_agent.run, daemon=True)
    thread.start()
    time.sleep(1.5)
    assert thread.is_alive(), "la boucle devrait tourner"

    started = time.monotonic()
    offline_agent.request_stop()
    thread.join(timeout=10)

    assert not thread.is_alive(), "la boucle ne s'est pas terminée sur demande"
    # Le gestionnaire de services laisse une trentaine de secondes ; on doit
    # rester très en deçà pour garder de la marge sur une machine chargée.
    assert time.monotonic() - started < 5


def test_stop_is_honoured_during_reconnection_backoff(offline_agent):
    """L'arrêt doit aboutir même pendant une attente de reconnexion.

    C'est le cas qui piégeait l'ancienne implémentation : `time.sleep()` ne
    regardait aucun signal, l'arrêt attendait donc la fin du délai.
    """
    thread = threading.Thread(target=offline_agent.run, daemon=True)
    thread.start()
    # Laisser plusieurs échecs s'enchaîner pour entrer dans le repli.
    time.sleep(3)

    offline_agent.request_stop()
    thread.join(timeout=10)
    assert not thread.is_alive()


def test_stop_before_start_ends_immediately(offline_agent):
    """Un arrêt demandé avant le démarrage ne doit pas lancer un tour de boucle."""
    offline_agent.request_stop()
    thread = threading.Thread(target=offline_agent.run, daemon=True)
    thread.start()
    thread.join(timeout=5)
    assert not thread.is_alive()


# ------------------------------------------------- ancrage des chemins


def test_buffer_is_anchored_on_the_config_not_the_cwd(offline_agent, tmp_path, monkeypatch):
    """Un service démarre dans System32 : le tampon ne doit pas y atterrir.

    `session.json` contient la clé d'authentification en clair — la voir
    apparaître dans un répertoire système au gré du répertoire courant serait
    à la fois une fuite et une perte d'état.
    """
    monkeypatch.chdir(tmp_path)  # simule un répertoire courant arbitraire
    anchored = resolve_buffer_dir("data/agent-buffer", str(tmp_path / "sub" / "config.yaml"))
    assert anchored == tmp_path / "sub" / "data" / "agent-buffer"
    assert tmp_path not in anchored.parents or "sub" in str(anchored)


def test_absolute_buffer_path_is_left_alone():
    absolute = resolve_buffer_dir("C:/ProgramData/CBC Agent/buffer")
    assert absolute.is_absolute()
    assert absolute.as_posix().endswith("CBC Agent/buffer")


def test_service_module_exposes_the_scm_contract():
    """Le module doit fournir ce que le gestionnaire de services attend.

    Son absence était le blocage : le binaire ne se déclarait jamais auprès du
    SCM, d'où l'échec 1053 « le service n'a pas répondu assez vite ».
    """
    import windows_service

    assert windows_service.SERVICE_NAME == "CBCAgent"
    if not windows_service.PYWIN32_AVAILABLE:
        pytest.skip("pywin32 absent — mode service indisponible sur cette plateforme")

    service = windows_service.CBCAgentService
    for handler in ("SvcDoRun", "SvcStop"):
        assert callable(getattr(service, handler, None)), f"{handler} manquant"
    assert service._svc_name_ == "CBCAgent"
