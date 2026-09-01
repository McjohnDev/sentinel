"""Relevés d'après le plan (point 7).

La règle qui traverse ces tests : **« je n'ai pas pu savoir » n'est pas
« non »**. C'est la distinction que la plateforme exploite, et la confondre
éteindrait une alerte « fichier interdit » ou « service arrêté » au moment
précis où l'agent perd la capacité de vérifier.
"""

from __future__ import annotations

import os

import pytest

import collectors
from collectors import RUNNING, STOPPED, UNKNOWN, disks, file_state, files, observe, services


# ------------------------------------------------------------------ disques


def test_a_named_partition_is_measured(tmp_path):
    reported = disks([str(tmp_path)])
    assert len(reported) == 1
    row = reported[0]
    assert row["mount"] == str(tmp_path)
    assert 0 <= row["percent"] <= 100
    assert row["total_gb"] > 0


def test_only_the_named_partitions_are_measured(tmp_path):
    # Interroger tous les volumes montés ferait dépendre le battement d'un
    # partage réseau figé — ce que la supervision doit signaler, pas subir.
    assert disks([]) == []
    assert len(disks([str(tmp_path)])) == 1


def test_an_unreadable_partition_is_reported_not_omitted():
    reported = disks(["/chemin/qui/n/existe/pas"])
    assert len(reported) == 1, "une partition qui disparaît doit se voir"
    # L'omettre éteindrait son alerte sans que personne ne l'ait décidé.
    assert reported[0]["percent"] is None
    assert reported[0]["error"] == "unreadable"


def test_an_empty_mount_name_is_skipped():
    assert disks([None, ""]) == []


# ----------------------------------------------------------------- fichiers


def test_an_existing_file_is_reported_with_its_size(tmp_path):
    target = tmp_path / "swift.log"
    target.write_text("x" * 120, encoding="utf-8")

    state = file_state(str(target))

    assert state["exists"] is True
    assert state["size_bytes"] == 120
    assert state["last_modified"]


def test_a_missing_file_is_a_definite_no(tmp_path):
    state = file_state(str(tmp_path / "absent.flag"))
    assert state["exists"] is False


def test_an_undecidable_file_is_neither_yes_nor_no(monkeypatch, tmp_path):
    """Le cœur du point 7 : l'indécidable se dit `None`.

    Traiter un accès refusé comme une absence lèverait une fausse alerte
    « fichier manquant » et, plus grave, éteindrait une alerte « fichier
    interdit » — au moment même où l'on perd la capacité de vérifier.
    """
    def refuse(_path):
        raise PermissionError("accès refusé")

    monkeypatch.setattr(collectors.os, "stat", refuse)

    state = file_state(str(tmp_path / "quelconque"))
    assert state["exists"] is None
    assert state["exists"] is not False


def test_a_path_through_a_file_is_a_definite_no(tmp_path):
    parent = tmp_path / "fichier"
    parent.write_text("x", encoding="utf-8")
    state = file_state(str(parent / "impossible"))
    assert state["exists"] is False


def test_files_accept_both_shapes_the_plan_uses(tmp_path):
    present = tmp_path / "a.log"
    present.write_text("x", encoding="utf-8")

    observed = files([str(present), {"path": str(tmp_path / "b.log")}])

    assert [o["exists"] for o in observed] == [True, False]


def test_a_file_entry_without_a_path_is_skipped():
    assert files([{}, None, ""]) == []


# ----------------------------------------------------------------- services


def test_an_unknown_service_is_unknown_not_stopped():
    # Déclarer « arrêté » un service qu'on n'a pas pu lire déclencherait une
    # alerte sur une ignorance.
    assert collectors.service_status("service-qui-nexiste-absolument-pas") == UNKNOWN


def test_an_empty_service_name_is_unknown():
    assert collectors.service_status("") == UNKNOWN


def test_services_reports_one_row_per_requested_name():
    rows = services(["a", "b"])
    assert [r["name"] for r in rows] == ["a", "b"]
    assert all(r["status"] in (RUNNING, STOPPED, UNKNOWN) for r in rows)


def test_a_running_service_is_seen(monkeypatch):
    monkeypatch.setattr(collectors, "service_status", lambda _n: RUNNING)
    assert services(["swift"])[0]["status"] == RUNNING


@pytest.mark.parametrize(
    "output,expected",
    [("active\n", RUNNING), ("inactive\n", STOPPED), ("failed\n", STOPPED), ("unknown\n", UNKNOWN)],
)
def test_systemd_states_are_normalised(monkeypatch, output, expected):
    monkeypatch.setattr(collectors, "_run", lambda _c: output)
    assert collectors._systemd_service_status("nginx") == expected


def test_an_unavailable_service_manager_yields_unknown(monkeypatch):
    monkeypatch.setattr(collectors, "_run", lambda _c: None)
    assert collectors._systemd_service_status("nginx") == UNKNOWN


# --------------------------------------------------------- lecture du plan


PLAN = {
    "services_monitoring": {"enabled": True, "services": ["swift-alliance"]},
    "files_monitoring": {"enabled": True, "files": [{"path": "/var/lock/cbc.flag"}]},
    "metrics": {"disk": {"alert_mounts": []}},
}


def test_observe_reads_every_section():
    out = observe(PLAN)
    assert [s["name"] for s in out["services"]] == ["swift-alliance"]
    assert [f["path"] for f in out["files"]] == ["/var/lock/cbc.flag"]
    assert out["disks"] == []


def test_no_plan_observes_nothing():
    # La plateforme n'évalue que ce qui est rapporté : un agent sans plan ne
    # doit rien affirmer, pas affirmer le vide.
    out = observe(None)
    assert out == {"disks": [], "services": [], "files": []}


def test_a_disabled_section_is_not_observed():
    plan = {"services_monitoring": {"enabled": False, "services": ["swift"]}}
    assert observe(plan)["services"] == []


@pytest.mark.parametrize(
    "shape",
    [
        {},
        {"metrics": None},
        {"services_monitoring": "oui"},
        {"metrics": {"disk": 3}},
        {"files_monitoring": {"files": "un-seul-chemin"}},
        {"services_monitoring": {"services": None}},
    ],
)
def test_a_malformed_plan_observes_nothing_instead_of_crashing(shape):
    """Un plan déformé ne doit pas faire taire l'hôte.

    Cesser de battre à cause d'un défaut de configuration est bien pire que
    de ne rien observer : la machine disparaîtrait du parc pour une raison
    qui n'a rien à voir avec elle.
    """
    out = observe(shape)
    assert out == {"disks": [], "services": [], "files": []}
