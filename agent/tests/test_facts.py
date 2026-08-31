"""Ce que l'agent constate de son hôte."""

from __future__ import annotations

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
    host = collect(AGENT_VERSION)
    assert host.runtime["agent_version"] == AGENT_VERSION
    assert "executable" in host.runtime
    assert isinstance(host.runtime["frozen"], bool)
