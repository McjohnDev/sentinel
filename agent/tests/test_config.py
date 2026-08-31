"""Lecture de la configuration de l'agent."""

from __future__ import annotations

import pytest

from config import ENROLLMENT_TOKEN_ENV, SERVER_URL_ENV, ConfigError, load_config

BASE = """
server:
  url: "https://plateforme.cbc:8443"
  enrollment_token: "jeton-du-fichier"
  tls_verify: true
agent:
  machine_type: "server"
"""


def _write(tmp_path, text):
    path = tmp_path / "config.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_reads_the_file(tmp_path):
    config = load_config(_write(tmp_path, BASE))
    assert config.server_url == "https://plateforme.cbc:8443"
    assert config.enrollment_token == "jeton-du-fichier"
    assert config.machine_type == "server"
    assert config.enroll_url == "https://plateforme.cbc:8443/api/agents/enroll"


def test_command_line_token_wins_over_the_file(tmp_path):
    # Le fichier livré avec le binaire ne doit jamais imposer son jeton à
    # l'exploitant qui installe.
    config = load_config(_write(tmp_path, BASE), token_override="jeton-de-la-ligne")
    assert config.enrollment_token == "jeton-de-la-ligne"


def test_environment_is_used_when_no_argument(tmp_path, monkeypatch):
    monkeypatch.setenv(ENROLLMENT_TOKEN_ENV, "jeton-environnement")
    monkeypatch.setenv(SERVER_URL_ENV, "https://autre.cbc")
    config = load_config(_write(tmp_path, BASE))
    assert config.enrollment_token == "jeton-environnement"
    assert config.server_url == "https://autre.cbc"


def test_plain_http_does_not_claim_to_verify_a_certificate(tmp_path):
    # Prétendre vérifier un certificat absent produit un échec TLS obscur au
    # premier enrôlement de laboratoire.
    config = load_config(_write(tmp_path, BASE.replace("https://plateforme.cbc:8443", "http://127.0.0.1:8443")))
    assert config.tls_verify is False


def test_missing_url_is_refused_with_a_usable_message(tmp_path):
    with pytest.raises(ConfigError) as exc:
        load_config(_write(tmp_path, "server:\n  enrollment_token: \"x\"\n"))
    assert "URL" in str(exc.value)


def test_unknown_machine_type_is_refused(tmp_path):
    with pytest.raises(ConfigError):
        load_config(_write(tmp_path, BASE.replace('"server"', '"routeur"')))


def test_broken_yaml_is_reported_as_configuration(tmp_path):
    with pytest.raises(ConfigError):
        load_config(_write(tmp_path, "server: [unclosed\n"))


def test_missing_file_is_reported_as_configuration(tmp_path):
    with pytest.raises(ConfigError):
        load_config(tmp_path / "absent.yaml")


def test_shipped_config_carries_no_token():
    # Ce fichier part dans chaque installation : un secret y serait diffusé.
    from pathlib import Path

    import yaml

    shipped = Path(__file__).resolve().parents[1] / "config.yaml"
    raw = yaml.safe_load(shipped.read_text(encoding="utf-8"))
    assert not (raw["server"]["enrollment_token"] or "").strip()
    assert raw["server"]["tls_verify"] is True
