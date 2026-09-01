"""Commandes de l'agent, telles qu'un exploitant les tape.

Cette couche n'était couverte par aucun test alors qu'elle porte toute la
surface d'usage — et elle s'est cassée deux fois pendant sa construction, sur
une simple faute de frappe qu'aucune suite ne signalait.

Les tests portent sur ce qu'un exploitant constate : le code de sortie et le
message. Un script d'installation silencieuse ne lit rien d'autre.
"""

from __future__ import annotations

import json

import pytest
import requests

import cli
import enrollment as enrollment_module
import runner as runner_module
from enrollment import Credentials, write_credentials


@pytest.fixture
def config_file(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(
        "server:\n"
        '  url: "https://plateforme.cbc:8443"\n'
        '  enrollment_token: ""\n'
        "  tls_verify: true\n"
        "agent:\n"
        '  machine_type: "server"\n',
        encoding="utf-8",
    )
    return path


def _run(argv, config_file=None):
    if config_file is not None:
        argv = ["--config", str(config_file)] + argv
    return cli.main(argv)


# ------------------------------------------------------------ commandes nues


def test_no_command_prints_help_and_fails():
    # Un script qui appelle l'agent sans verbe doit le savoir par le code de
    # sortie, pas seulement par le texte.
    assert cli.main([]) == 2


def test_version_succeeds(capsys):
    assert cli.main(["version"]) == 0
    assert capsys.readouterr().out.strip()


def test_the_parser_accepts_every_advertised_command():
    # Garde-fou contre une commande annoncée dans l'aide mais non branchée.
    parser = cli.build_parser()
    for verb in ("enroll", "uninstall", "run", "status", "version"):
        args = parser.parse_args([verb])
        assert hasattr(args, "func"), verb


# -------------------------------------------------------------------- status


def test_status_on_a_fresh_host_says_what_to_do(capsys):
    assert cli.main(["status"]) == 0
    out = capsys.readouterr().out
    assert "aucun" in out.lower()
    assert "enroll" in out


def test_status_shows_the_link_as_the_host_sees_it(capsys):
    import session as session_module

    write_credentials(Credentials("A3F09C", "cle"))
    session_module.record_failure(
        server_url="https://plateforme.cbc:8443", agent_id="A3F09C", error="coupure réseau"
    )

    assert cli.main(["status"]) == 0

    out = capsys.readouterr().out
    assert "A3F09C" in out
    assert "rompue" in out
    assert "coupure réseau" in out


# -------------------------------------------------------------------- enroll


def test_enroll_without_a_token_fails_before_touching_the_host(config_file, capsys, isolated_state):
    assert _run(["enroll"], config_file) == 2
    assert "jeton" in capsys.readouterr().err.lower()
    # Rien n'a été écrit : ni identité, ni jetons.
    assert not (isolated_state / "machine_id").exists()
    assert not (isolated_state / "credentials.json").exists()


def test_enroll_on_an_already_enrolled_host_does_not_spend_a_token(config_file, capsys):
    write_credentials(Credentials("A3F09C", "cle"))
    assert _run(["enroll", "--token", "jeton-de-test-001"], config_file) == 0
    assert "déjà enrôlé" in capsys.readouterr().out


def test_enroll_reports_an_unreachable_platform(config_file, capsys, monkeypatch):
    def refuse(*_a, **_k):
        raise enrollment_module.EnrollmentError("Plateforme injoignable sur https://x : coupure")

    monkeypatch.setattr(cli, "enroll", refuse)
    assert _run(["enroll", "--token", "jeton-de-test-001"], config_file) == 1
    assert "injoignable" in capsys.readouterr().err


def test_a_broken_configuration_is_named(tmp_path, capsys):
    bad = tmp_path / "config.yaml"
    bad.write_text("server: [pas ferme\n", encoding="utf-8")
    assert _run(["enroll", "--token", "jeton-de-test-001"], bad) == 2
    assert "Configuration" in capsys.readouterr().err


# ----------------------------------------------------------------- uninstall


def test_uninstall_on_a_host_that_was_never_enrolled_is_not_an_error(config_file, capsys):
    assert _run(["uninstall"], config_file) == 0
    assert "pas enrôlé" in capsys.readouterr().out


def test_uninstall_keeps_the_credentials_when_the_platform_cannot_be_told(
    config_file, capsys, monkeypatch
):
    """La règle du point 4, vérifiée par la commande et non par la fonction."""
    write_credentials(Credentials("A3F09C", "cle"))

    def refuse(*_a, **_k):
        raise enrollment_module.DeregistrationError("Plateforme injoignable")

    monkeypatch.setattr(cli, "deregister", refuse)

    assert _run(["uninstall"], config_file) == 1
    assert enrollment_module.read_credentials() is not None, "les jetons doivent survivre"
    assert "--force" in capsys.readouterr().err


def test_uninstall_force_clears_but_still_exits_non_zero(config_file, capsys, monkeypatch):
    # Le code non nul est délibéré : la plateforme croit toujours l'hôte vivant.
    write_credentials(Credentials("A3F09C", "cle"))
    monkeypatch.setattr(
        cli, "deregister", lambda *a, **k: (_ for _ in ()).throw(
            enrollment_module.DeregistrationError("injoignable")
        )
    )

    assert _run(["uninstall", "--force"], config_file) == 1
    assert enrollment_module.read_credentials() is None


def test_a_successful_uninstall_clears_and_succeeds(config_file, capsys, monkeypatch):
    write_credentials(Credentials("A3F09C", "cle"))
    monkeypatch.setattr(cli, "deregister", lambda *a, **k: "A3F09C")

    assert _run(["uninstall", "--reason", "poste réformé"], config_file) == 0
    assert enrollment_module.read_credentials() is None
    assert "A3F09C" in capsys.readouterr().out


# ----------------------------------------------------------------------- run


def test_run_refuses_on_a_host_that_is_not_enrolled(config_file, capsys):
    assert _run(["run"], config_file) == 2
    assert "non enrôlé" in capsys.readouterr().err


def test_run_once_performs_a_single_beat(config_file, monkeypatch):
    write_credentials(Credentials("A3F09C", "cle"))
    seen = {}

    def fake_run(config, creds, host, **kwargs):
        seen.update(kwargs)
        return runner_module.RunnerOutcome(beats_sent=1)

    monkeypatch.setattr(cli, "run_loop", fake_run)

    assert _run(["run", "--once"], config_file) == 0
    assert seen["max_beats"] == 1


def test_run_without_once_loops_indefinitely(config_file, monkeypatch):
    write_credentials(Credentials("A3F09C", "cle"))
    seen = {}
    monkeypatch.setattr(
        cli, "run_loop",
        lambda c, cr, h, **kw: (seen.update(kw), runner_module.RunnerOutcome(beats_sent=1))[1],
    )

    assert _run(["run"], config_file) == 0
    assert seen["max_beats"] is None


def test_run_reports_when_no_beat_was_ever_accepted(config_file, capsys, monkeypatch):
    write_credentials(Credentials("A3F09C", "cle"))
    monkeypatch.setattr(
        cli, "run_loop",
        lambda *a, **k: runner_module.RunnerOutcome(beats_sent=0, last_error="Plateforme injoignable"),
    )

    assert _run(["run"], config_file) == 1
    assert "injoignable" in capsys.readouterr().err


def test_an_interrupted_run_exits_cleanly(config_file, capsys, monkeypatch):
    # Ctrl+C est la façon normale d'arrêter un agent lancé à la main.
    write_credentials(Credentials("A3F09C", "cle"))

    def interrupted(*_a, **_k):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "run_loop", interrupted)

    assert _run(["run"], config_file) == 0
    assert "Arrêt" in capsys.readouterr().out


def test_the_lock_is_released_when_the_run_ends(config_file, monkeypatch, isolated_state):
    import instance_lock

    write_credentials(Credentials("A3F09C", "cle"))
    monkeypatch.setattr(cli, "run_loop", lambda *a, **k: runner_module.RunnerOutcome(beats_sent=1))

    _run(["run", "--once"], config_file)

    # Sans libération, un redémarrage immédiat serait refusé.
    assert instance_lock.read_holder() is None


def test_a_second_run_is_refused_while_one_holds_the_lock(config_file, capsys, monkeypatch):
    import os

    import instance_lock

    write_credentials(Credentials("A3F09C", "cle"))
    # Un autre processus vivant détient le verrou : on emprunte le PID du
    # processus de test, qui est vivant par construction.
    instance_lock.lock_file().parent.mkdir(parents=True, exist_ok=True)
    instance_lock.lock_file().write_text("%d\n" % os.getppid(), encoding="utf-8")
    monkeypatch.setattr(instance_lock, "_process_alive", lambda _pid: True)

    assert _run(["run"], config_file) == 2
    assert "déjà" in capsys.readouterr().err
