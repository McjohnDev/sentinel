"""Ce que l'agent constate de son hôte."""

from __future__ import annotations

import facts
from facts import collect, sanitize_hostname
from enrollment import AGENT_VERSION


def test_hostname_is_reduced_to_what_the_platform_accepts():
    # La plateforme valide `^[a-zA-Z0-9\-_\.]+$`. Un poste nommé
    # « PC-Comptabilité » partait sinon en 422 au moment de l'installation,
    # avec un message que personne sur site ne peut interpréter.
    assert sanitize_hostname("PC-Comptabilité") == "PC-Comptabilit"
    assert sanitize_hostname("poste bureau 3") == "poste-bureau-3"
    assert sanitize_hostname("web-01.prod") == "web-01.prod"


def test_hostname_never_comes_back_empty():
    assert sanitize_hostname("") == "hote-inconnu"
    assert sanitize_hostname("!!!") == "hote-inconnu"


def test_hostname_is_bounded():
    assert len(sanitize_hostname("a" * 400)) == 255


def test_collect_describes_this_host():
    host = collect(AGENT_VERSION)
    assert host.hostname
    assert host.os
    assert host.os_version
    # Caractéristiques matérielles : mesurées ou explicitement absentes,
    # jamais zéro — une machine sans processeur n'existe pas, et un 0 dans
    # l'inventaire se lirait comme une mesure.
    for value in (host.cpu_cores, host.ram_total_gb, host.disk_total_gb):
        assert value is None or value > 0


def test_runtime_says_how_the_agent_runs():
    # Champs renommés au point 10 pour correspondre à ce que la fiche d'hôte
    # affiche : `executable` et `frozen` ne s'y lisaient nulle part.
    host = collect(AGENT_VERSION)
    assert host.runtime["agent_version"] == AGENT_VERSION
    assert host.runtime["executable_path"]
    assert host.runtime["packaging"] in ("source", "pyinstaller")


# ------------------------------------------ où et comment l'agent tourne (point 10)


def test_the_runtime_carries_the_fields_the_host_record_displays():
    """Les noms doivent correspondre à ce que le panneau lit.

    Un relevé qui ne porte pas les mêmes clés produit un écran vide sans
    qu'aucune erreur ne se produise nulle part — le pire des défauts, parce
    qu'il ressemble à « rien à afficher ».
    """
    from enrollment import AGENT_VERSION

    info = facts.runtime_info(AGENT_VERSION)
    for key in (
        "run_mode", "run_as_user", "elevated", "executable_path", "install_dir",
        "packaging", "platform", "python_version", "pid", "uptime_seconds",
    ):
        assert key in info, key


def test_the_configuration_is_described_when_known():
    from config import AgentConfig
    from enrollment import AGENT_VERSION

    cfg = AgentConfig("https://p.cbc:8443", "", True, "server", 5, source_path="/etc/cbc.yaml")
    info = facts.runtime_info(AGENT_VERSION, cfg)

    # Un hôte qui bat vers la mauvaise plateforme se diagnostique ici.
    assert info["server_url"] == "https://p.cbc:8443"
    assert info["tls_verify"] is True
    assert info["config_path"] == "/etc/cbc.yaml"


def test_the_run_mode_can_be_declared(monkeypatch):
    # Un agent lancé à la main disparaît à la fermeture de session, ce qui
    # explique un hôte qui « retombe hors ligne tous les soirs ».
    monkeypatch.setenv("CBC_AGENT_RUN_MODE", "console")
    assert facts._run_mode() == "console"
    monkeypatch.setenv("CBC_AGENT_RUN_MODE", "service")
    assert facts._run_mode() == "service"


def test_an_absurd_declared_mode_is_ignored(monkeypatch):
    monkeypatch.setenv("CBC_AGENT_RUN_MODE", "peut-etre")
    assert facts._run_mode() in ("console", "service", "unknown")


def test_packaging_says_whether_the_agent_is_frozen():
    from enrollment import AGENT_VERSION

    assert facts.runtime_info(AGENT_VERSION)["packaging"] in ("source", "pyinstaller")


def test_elevation_is_reported_or_admitted_unknown():
    # Sans élévation, certains services remontent « inconnu » plutôt que leur
    # état réel : l'exploitant doit pouvoir faire le lien.
    from enrollment import AGENT_VERSION

    assert facts.runtime_info(AGENT_VERSION)["elevated"] in (True, False, None)


def test_a_service_run_names_the_service(monkeypatch):
    from enrollment import AGENT_VERSION

    monkeypatch.setenv("CBC_AGENT_RUN_MODE", "service")
    monkeypatch.setenv("CBC_AGENT_SERVICE_NAME", "cbc-agent-prod")
    assert facts.runtime_info(AGENT_VERSION)["service_name"] == "cbc-agent-prod"
