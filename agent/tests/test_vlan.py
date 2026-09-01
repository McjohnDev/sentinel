"""VLAN constaté par l'hôte.

Le point délicat n'est pas la détection, c'est ce que l'absence signifie. Une
machine sur port d'accès ne voit pas son VLAN : le commutateur pose et retire
l'étiquette sans que l'hôte en sache rien. `None` veut donc dire « non
déterminable depuis l'hôte », jamais « aucun VLAN » — d'où le champ déclaré
par l'exploitation, qui lui existe pour tous les hôtes.
"""

from __future__ import annotations

import facts
from facts import _single, detect_vlan


def test_a_single_tagged_vlan_is_reported():
    assert _single(["100"]) == "100"


def test_several_tagged_vlans_are_all_reported():
    # Un hôte sur port trunk peut en porter plusieurs. En choisir un seul
    # serait arbitraire et faux dans l'inventaire.
    assert _single(["300", "100", "200"]) == "100,200,300"


def test_duplicates_collapse():
    assert _single(["100", "100"]) == "100"


def test_an_untagged_host_reports_nothing():
    assert _single([]) is None


def test_out_of_range_identifiers_are_rejected():
    # 0 et 4095 sont réservés ; au-delà, ce n'est pas un VLAN 802.1Q.
    assert _single(["0"]) is None
    assert _single(["4095"]) is None
    assert _single(["9999"]) is None
    assert _single(["abc"]) is None


def test_the_proc_table_is_read_when_present(tmp_path, monkeypatch):
    table = tmp_path / "config"
    table.write_text(
        "VLAN Dev name\t | VLAN ID\n"
        "Name-Type: VLAN_NAME_TYPE_RAW_PLUS_VID_NO_PAD\n"
        "eth0.100       | 100  | eth0\n"
        "eth0.250       | 250  | eth0\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(facts, "_PROC_VLAN", str(table))
    assert facts._vlan_from_proc() == "100,250"


def test_the_proc_header_is_not_mistaken_for_a_vlan(tmp_path, monkeypatch):
    table = tmp_path / "config"
    table.write_text("VLAN Dev name\t | VLAN ID\nName-Type: VLAN_NAME_TYPE_RAW\n", encoding="utf-8")
    monkeypatch.setattr(facts, "_PROC_VLAN", str(table))
    assert facts._vlan_from_proc() is None


def test_a_missing_proc_table_is_not_an_error(monkeypatch):
    # Windows, macOS, ou un noyau sans module 8021q.
    monkeypatch.setattr(facts, "_PROC_VLAN", "/chemin/qui/n/existe/pas")
    assert facts._vlan_from_proc() is None


def test_interface_names_are_the_fallback(monkeypatch):
    monkeypatch.setattr(facts, "_PROC_VLAN", "/absent")
    monkeypatch.setattr(
        facts.psutil, "net_if_addrs", lambda: {"lo": [], "eth0": [], "eth0.42": [], "bond0.7": []}
    )
    assert facts._vlan_from_interface_names() == "7,42"


def test_an_ordinary_interface_is_not_read_as_a_vlan(monkeypatch):
    monkeypatch.setattr(facts, "_PROC_VLAN", "/absent")
    monkeypatch.setattr(
        facts.psutil, "net_if_addrs", lambda: {"eth0": [], "Wi-Fi": [], "Ethernet 2": []}
    )
    assert facts._vlan_from_interface_names() is None


def test_detect_vlan_never_raises_on_this_host():
    # Quelle que soit la plateforme qui exécute les tests, la détection doit
    # rendre une valeur ou None — jamais faire échouer un enrôlement.
    result = detect_vlan()
    assert result is None or result.replace(",", "").isdigit()


def test_host_facts_carry_the_observed_vlan():
    from enrollment import AGENT_VERSION

    host = facts.collect(AGENT_VERSION)
    assert host.vlan_observed is None or host.vlan_observed.replace(",", "").isdigit()
