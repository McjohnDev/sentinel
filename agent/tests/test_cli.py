"""CLI de l'agent : analyse des arguments, validation, désinstallation.

Le défaut corrigé ici est le plus grave du paquet : l'agent testait
`sys.argv[1].endswith('.yaml')` au lieu d'analyser ses arguments. Comme tous
les services installés (systemd, launchd, MSI, install.sh) le lancent avec
`--config /etc/cbc-agent/config.yaml`, `--config` était pris pour une URL de
serveur et le chemin du fichier pour un jeton d'enrôlement. **Aucun agent
installé hors Docker ne chargeait sa configuration** — et rien ne le disait.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
AGENT_SRC = Path(__file__).resolve().parents[1] / "src"
for p in (str(ROOT), str(AGENT_SRC)):
    if p not in sys.path:
        sys.path.insert(0, p)

import cli  # noqa: E402


def _write_config(tmp_path: Path, **overrides) -> Path:
    config = {
        "server": {"url": "https://sentinel.cbcam.cm:8443", "tls_verify": True},
        "agent": {"heartbeat_interval": 30, "ping_interval": 10, "machine_type": "server"},
        "degraded_mode": {"buffer_dir": str(tmp_path / "buffer")},
    }
    for section, values in overrides.items():
        config.setdefault(section, {}).update(values)
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    return path


# ------------------------------------------------- analyse des arguments


def test_installed_service_command_line_is_understood():
    """`cbc-agent --config /etc/...` — la ligne ExecStart de tous les paquets.

    C'est LE cas qui ne fonctionnait pas. Sans sous-commande explicite,
    l'intention d'un service est de superviser.
    """
    assert cli._legacy_argv(["--config", "/etc/cbc-agent/config.yaml"]) == [
        "run",
        "--config",
        "/etc/cbc-agent/config.yaml",
    ]


def test_docker_positional_form_still_works():
    """L'image Docker lance `agent.py /app/config.yaml` — à ne pas casser."""
    assert cli._legacy_argv(["/app/config.yaml"]) == ["run", "--config", "/app/config.yaml"]
    assert cli._legacy_argv(["conf.yml"]) == ["run", "--config", "conf.yml"]


def test_legacy_url_and_token_form_still_works():
    assert cli._legacy_argv(["https://srv:8443", "jeton-1"]) == [
        "run",
        "--server",
        "https://srv:8443",
        "--token",
        "jeton-1",
    ]


@pytest.mark.parametrize(
    "argv",
    [["run", "--config", "x.yaml"], ["status"], ["uninstall"], ["--help"], ["--version"], []],
)
def test_explicit_forms_are_left_alone(argv):
    assert cli._legacy_argv(argv) is None


def test_config_flag_actually_reaches_the_parser():
    """La régression de fond : `--config` doit produire un chemin exploitable."""
    args = cli.build_parser().parse_args(["run", "--config", "/etc/cbc-agent/config.yaml"])
    assert args.config == "/etc/cbc-agent/config.yaml"
    assert cli.resolve_config_path(args.config) == "/etc/cbc-agent/config.yaml"


def test_every_subcommand_accepts_config_except_version():
    parser = cli.build_parser()
    for verb in ("run", "enroll", "uninstall", "status", "validate-config"):
        assert parser.parse_args([verb, "--config", "c.yaml"]).config == "c.yaml"


# -------------------------------------------------------------- résolution


def test_environment_variable_is_honoured(tmp_path, monkeypatch):
    monkeypatch.setenv("CBC_AGENT_CONFIG", "/opt/cbc/config.yaml")
    assert cli.resolve_config_path(None) == "/opt/cbc/config.yaml"


def test_explicit_flag_beats_environment(monkeypatch):
    monkeypatch.setenv("CBC_AGENT_CONFIG", "/opt/cbc/config.yaml")
    assert cli.resolve_config_path("/tmp/autre.yaml") == "/tmp/autre.yaml"


# -------------------------------------------------------------- validation


def test_valid_configuration_passes(tmp_path):
    path = _write_config(tmp_path)
    ok, blocking, _warnings = cli.validate_config(cli.load_config(str(path)), str(path))
    assert ok, blocking


def test_empty_enrollment_token_is_reported(tmp_path):
    """Le piège silencieux du fichier livré.

    `enrollment_token: ""` — la clé *existe*, donc `.get(clé, défaut)` renvoie
    la chaîne vide et non le repli. L'enrôlement bouclait indéfiniment sans
    message distinctif.
    """
    path = _write_config(tmp_path, server={"enrollment_token": ""})
    ok, blocking, warnings = cli.validate_config(cli.load_config(str(path)), str(path))
    # Signalé, mais non bloquant : un agent déjà enrôlé n'a plus besoin de
    # jeton et doit continuer à superviser.
    assert ok and not blocking
    assert any("enrollment_token" in w for w in warnings)


def test_missing_server_url_is_reported(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump({"agent": {}}), encoding="utf-8")
    ok, blocking, _warnings = cli.validate_config(cli.load_config(str(path)), str(path))
    assert not ok
    assert any("server.url" in p for p in blocking)


def test_plaintext_url_warns_without_blocking_startup(tmp_path):
    """Le clair doit se voir — sans immobiliser une supervision qui marche.

    Refuser de démarrer là-dessus arrêterait les piles de laboratoire, qui
    tournent légitimement en HTTP : le remède serait pire que le mal.
    """
    path = _write_config(tmp_path, server={"url": "http://server:8000", "tls_verify": True})
    ok, blocking, warnings = cli.validate_config(cli.load_config(str(path)), str(path))
    assert ok and not blocking
    assert any("clair" in w for w in warnings)


def test_https_without_certificate_check_is_warned(tmp_path):
    path = _write_config(tmp_path, server={"url": "https://sentinel:8443", "tls_verify": False})
    ok, blocking, warnings = cli.validate_config(cli.load_config(str(path)), str(path))
    assert ok and not blocking
    assert any("tls_verify" in w for w in warnings)


def test_absent_file_is_reported_not_swallowed(tmp_path):
    ok, blocking, _warnings = cli.validate_config({}, None)
    assert not ok
    assert any("Aucun fichier de configuration" in p for p in blocking)


def test_empty_yaml_does_not_crash(tmp_path):
    """`yaml.safe_load` rend None sur un fichier vide — piège classique."""
    path = tmp_path / "config.yaml"
    path.write_text("", encoding="utf-8")
    assert cli.load_config(str(path)) == {}
    ok, blocking, _warnings = cli.validate_config(cli.load_config(str(path)), str(path))
    assert not ok and blocking


def test_invalid_machine_type_is_reported(tmp_path):
    path = _write_config(tmp_path, agent={"machine_type": "serveur"})
    ok, blocking, _warnings = cli.validate_config(cli.load_config(str(path)), str(path))
    assert not ok
    assert any("machine_type" in p for p in blocking)


# ----------------------------------------------------------- désinstallation


@pytest.fixture
def isolated_machine_id(tmp_path, monkeypatch):
    """Isole du poste tout l'état que la désinstallation efface.

    Sans cette isolation, le test effaçait le véritable `agent/.machine_id`
    **et le verrou de l'agent en cours d'exécution** sur la machine de
    développement. Une suite de tests ne doit rien modifier hors de son
    répertoire temporaire — a fortiori pas l'identité d'un agent en service.
    """
    from instance_lock import InstanceLock

    monkeypatch.setenv(InstanceLock.LOCK_DIR_ENV, str(tmp_path))

    path = tmp_path / "machine_id"
    path.write_text("id-de-test", encoding="utf-8")
    monkeypatch.setenv("AGENT_MACHINE_ID_FILE", str(path))
    return path


def test_uninstall_purges_the_stored_credentials(tmp_path, isolated_machine_id):
    """La clé d'authentification est stockée en clair : elle doit disparaître.

    La laisser sur un poste désinstallé, c'est abandonner un identifiant
    valide sur une machine qui n'est plus supervisée.
    """
    buffer_dir = tmp_path / "buffer"
    buffer_dir.mkdir()
    session = buffer_dir / "session.json"
    session.write_text('{"auth_key": "secret-vivant", "agent_id": "A3F09C"}', encoding="utf-8")
    (buffer_dir / "queue.jsonl").write_text("{}", encoding="utf-8")

    config = {"degraded_mode": {"buffer_dir": str(buffer_dir)}}
    removed = cli._purge_local_state(config)

    assert not session.exists(), "la clé d'authentification survit à la désinstallation"
    assert not (buffer_dir / "queue.jsonl").exists()
    assert not isolated_machine_id.exists(), "l'identifiant machine doit être effacé"
    assert len(removed) >= 3


def test_uninstall_targets_the_machine_id_the_agent_actually_uses(tmp_path, monkeypatch):
    """Le chemin doit suivre AGENT_MACHINE_ID_FILE, comme le fait l'agent.

    Codé en dur à côté du paquet, il effaçait sous Docker un fichier sans
    rapport et laissait le véritable identifiant dans son volume : l'hôte
    serait revenu sous la même identité après une désinstallation censée
    l'avoir effacée.
    """
    from instance_lock import InstanceLock

    monkeypatch.setenv(InstanceLock.LOCK_DIR_ENV, str(tmp_path))
    elsewhere = tmp_path / "volume" / "machine_id"
    elsewhere.parent.mkdir()
    elsewhere.write_text("id-en-volume", encoding="utf-8")
    monkeypatch.setenv("AGENT_MACHINE_ID_FILE", str(elsewhere))

    buffer_dir = tmp_path / "buffer"
    buffer_dir.mkdir()
    cli._purge_local_state({"degraded_mode": {"buffer_dir": str(buffer_dir)}})

    assert not elsewhere.exists()


def test_uninstall_reads_the_session_to_find_the_platform(tmp_path):
    buffer_dir = tmp_path / "buffer"
    buffer_dir.mkdir()
    (buffer_dir / "session.json").write_text(
        '{"auth_key": "k", "agent_id": "A3F09C", "server_url": "https://sentinel:8443"}',
        encoding="utf-8",
    )
    config = {"degraded_mode": {"buffer_dir": str(buffer_dir)}}
    session = cli.load_session(config)

    assert session["agent_id"] == "A3F09C"
    assert cli.server_url_from(config, session) == "https://sentinel:8443"


def test_config_url_wins_over_stale_session_url(tmp_path):
    """Un serveur redéployé ailleurs : le fichier fait foi, pas la session."""
    config = {"server": {"url": "https://nouveau:8443"}}
    session = {"server_url": "https://ancien:8443"}
    assert cli.server_url_from(config, session) == "https://nouveau:8443"
