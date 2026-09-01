"""Inventaire de l'hôte : services offerts, applications, pilotes.

Le relevé sert d'abord à ce que l'exploitant **choisisse** un service au lieu
de le taper : une faute de frappe produit une surveillance qui ne surveille
rien, et le service reste « inconnu » au lieu d'être « arrêté » — un écran
qui a l'air de fonctionner et ne protège personne.
"""

from __future__ import annotations

import subprocess

import pytest

import inventory
from inventory import Inventory, _fold_header, _pick, collect


# ------------------------------------------------- robustesse d'exécution


def test_a_missing_command_is_not_an_error(monkeypatch):
    def absent(*_a, **_k):
        raise FileNotFoundError("commande introuvable")

    monkeypatch.setattr(inventory.subprocess, "run", absent)
    assert inventory._run(["outil-inexistant"]) is None


def test_a_command_that_times_out_is_not_an_error(monkeypatch):
    def slow(*_a, **_k):
        raise subprocess.TimeoutExpired(cmd="x", timeout=1)

    monkeypatch.setattr(inventory.subprocess, "run", slow)
    assert inventory._run(["lent"]) is None


# --------------------------------------------- en-têtes localisées (Windows)


def test_headers_fold_across_languages():
    # Les outils console Windows sont traduits : coder les intitulés anglais
    # en dur donnait un inventaire silencieusement amputé sur un poste
    # français.
    assert _fold_header("État") == "etat"
    assert _fold_header("Nom du module") == "nomdumodule"
    assert _fold_header(" Module Name ") == "modulename"


def test_a_french_driver_row_is_read():
    record = {"Nom du module": "ACPI", "Nom complet": "Pilote ACPI", "État": "Running"}
    assert _pick(record, "modulename", "nomdumodule") == "ACPI"
    assert _pick(record, "displayname", "nomcomplet") == "Pilote ACPI"
    assert _pick(record, "state", "etat") == "Running"


def test_an_english_driver_row_is_read():
    record = {"Module Name": "ACPI", "Display Name": "ACPI Driver", "State": "Running"}
    assert _pick(record, "modulename", "nomdumodule") == "ACPI"
    assert _pick(record, "state", "etat") == "Running"


def test_state_is_not_confused_with_status():
    # Sur driverquery /V, « État » porte Running/Stopped et « Statut » porte
    # OK/Erreur. Les confondre remonterait « OK » comme état d'exécution.
    record = {"État": "Stopped", "Statut": "OK"}
    assert _pick(record, "state", "etat") == "Stopped"


def test_an_absent_column_yields_none():
    assert _pick({"Autre": "x"}, "state", "etat") is None


def test_an_empty_cell_yields_none():
    assert _pick({"État": "   "}, "state", "etat") is None


# --------------------------------------------------------------- systemd


def test_systemd_units_are_parsed(monkeypatch):
    monkeypatch.setattr(inventory.sys, "platform", "linux")
    monkeypatch.setattr(
        inventory, "_run",
        lambda _c: (
            "nginx.service loaded active running A high performance web server\n"
            "cron.service loaded inactive dead Regular background program\n"
        ),
    )
    rows = inventory.available_services()
    assert [r["name"] for r in rows] == ["nginx", "cron"]
    assert rows[0]["status"] == "running"
    assert rows[1]["status"] == "stopped"


def test_an_unavailable_service_manager_yields_no_services(monkeypatch):
    monkeypatch.setattr(inventory.sys, "platform", "linux")
    monkeypatch.setattr(inventory, "_run", lambda _c: None)
    assert inventory.available_services() == []


# --------------------------------------------------------- paquets Linux


def test_dpkg_packages_are_parsed(monkeypatch):
    monkeypatch.setattr(inventory.sys, "platform", "linux")
    monkeypatch.setattr(
        inventory, "_run",
        lambda cmd: "nginx\t1.18.0\tDebian\nopenssl\t3.0.2\tDebian\n" if cmd[0] == "dpkg-query" else None,
    )
    rows = inventory.applications()
    assert [r["name"] for r in rows] == ["nginx", "openssl"]
    assert rows[0]["version"] == "1.18.0"


def test_rpm_is_used_when_dpkg_is_absent(monkeypatch):
    monkeypatch.setattr(inventory.sys, "platform", "linux")
    monkeypatch.setattr(
        inventory, "_run",
        lambda cmd: None if cmd[0] == "dpkg-query" else "httpd\t2.4.6-97\tRed Hat\n",
    )
    rows = inventory.applications()
    assert rows[0]["name"] == "httpd"


def test_lsmod_modules_are_the_linux_drivers(monkeypatch):
    monkeypatch.setattr(inventory.sys, "platform", "linux")
    monkeypatch.setattr(inventory, "_run", lambda _c: "Module Size Used by\nxfs 1544192 1\nnf_tables 219136 0\n")
    rows = inventory.drivers()
    assert [r["name"] for r in rows] == ["xfs", "nf_tables"]


# -------------------------------------------------------------- assemblage


def test_a_missing_section_is_named_not_silently_empty(monkeypatch):
    # Un inventaire partiel ne doit pas se lire comme un hôte sans
    # applications : la différence change la conclusion qu'on en tire.
    monkeypatch.setattr(inventory, "available_services", lambda: [{"name": "nginx"}])
    monkeypatch.setattr(inventory, "applications", lambda: [])
    monkeypatch.setattr(inventory, "drivers", lambda: [{"name": "xfs"}])

    report = collect()

    assert "applications" in report.unavailable
    assert "services" not in report.unavailable


def test_a_section_that_raises_does_not_take_the_others_down(monkeypatch):
    def broken():
        raise RuntimeError("registre inaccessible")

    monkeypatch.setattr(inventory, "available_services", lambda: [{"name": "nginx"}])
    monkeypatch.setattr(inventory, "applications", broken)
    monkeypatch.setattr(inventory, "drivers", lambda: [])

    report = collect()

    assert report.services == [{"name": "nginx"}]
    assert "applications" in report.unavailable


def test_a_very_long_list_is_capped_and_says_so(monkeypatch):
    # Une troncature muette se lirait comme un inventaire complet.
    many = [{"name": "paquet-%d" % i} for i in range(inventory.MAX_ROWS + 50)]
    monkeypatch.setattr(inventory, "available_services", lambda: [])
    monkeypatch.setattr(inventory, "applications", lambda: many)
    monkeypatch.setattr(inventory, "drivers", lambda: [])

    report = collect()

    assert len(report.applications) == inventory.MAX_ROWS
    assert any("applications" in note for note in report.truncated)


def test_the_payload_carries_every_section():
    payload = Inventory(services=[{"name": "a"}]).as_payload()
    assert set(payload) == {"services", "applications", "drivers", "truncated", "unavailable"}


# ------------------------------------------------------------ transmission


class _Response:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


class _Session:
    def __init__(self, status=200, raises=None):
        self.status = status
        self.raises = raises
        self.calls = []

    def post(self, url, json=None, headers=None, timeout=None, verify=None):
        self.calls.append({"url": url, "json": json, "headers": headers})
        if self.raises:
            raise self.raises
        return _Response(self.status)


def test_the_inventory_is_sent_with_the_agent_key():
    from config import AgentConfig
    from enrollment import Credentials

    config = AgentConfig("https://p.cbc:8443", "", True, "server", 5)
    session = _Session()

    inventory.push(config, Credentials("A3F09C", "cle"), Inventory(services=[{"name": "a"}]), session=session)

    call = session.calls[0]
    assert call["url"] == "https://p.cbc:8443/api/agents/inventory"
    assert call["headers"]["Authorization"] == "cle"
    assert call["json"]["services"] == [{"name": "a"}]


def test_a_refused_inventory_is_reported():
    from config import AgentConfig
    from enrollment import Credentials

    config = AgentConfig("https://p.cbc:8443", "", True, "server", 5)
    with pytest.raises(inventory.InventoryPushFailed):
        inventory.push(config, Credentials("A", "c"), Inventory(), session=_Session(status=500))
