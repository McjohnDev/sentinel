"""Rebasculer un agent vers une autre plateforme.

Le passage du laboratoire a la production deplace la plateforme, pas les
machines. Desinstaller puis reinstaller le parc pour un simple changement
d'adresse ferait perdre a chaque hote son identite et son historique, et
consommerait un jeton par poste -- pour un parc de deux cents machines, c'est
une journee de travail et deux cents lignes de plus dans l'inventaire.

D'ou `configure` : l'adresse change, l'identite reste.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import cli  # noqa: E402


@pytest.fixture
def config_file(tmp_path):
    chemin = tmp_path / "config.yaml"
    chemin.write_text(
        yaml.safe_dump(
            {
                "server": {"url": "http://labo.local:8443", "tls_verify": False},
                "agent": {"machine_type": "workstation", "timeout_seconds": 15},
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    return chemin


@pytest.fixture(autouse=True)
def _isoler_etat(tmp_path, monkeypatch):
    """L'agent ne doit pas lire l'etat reel du poste qui execute les tests."""
    monkeypatch.setenv("CBC_AGENT_STATE_DIR", str(tmp_path / "etat"))
    monkeypatch.setattr(cli, "is_enrolled", lambda: False)


def _lire(chemin):
    return yaml.safe_load(chemin.read_text(encoding="utf-8"))


def test_the_platform_address_is_replaced(config_file):
    code = cli.main(["--config", str(config_file), "configure", "--server-url", "https://prod.cbc.cm"])

    assert code == 0
    assert _lire(config_file)["server"]["url"] == "https://prod.cbc.cm"


def test_the_rest_of_the_configuration_survives(config_file):
    """Reecrire le fichier entier effacerait le type de machine et le delai."""
    cli.main(["--config", str(config_file), "configure", "--server-url", "https://prod.cbc.cm"])

    agent = _lire(config_file)["agent"]
    assert agent["machine_type"] == "workstation"
    assert agent["timeout_seconds"] == 15


def test_certificate_checking_is_left_alone_unless_asked(config_file):
    cli.main(["--config", str(config_file), "configure", "--server-url", "https://prod.cbc.cm"])
    assert _lire(config_file)["server"]["tls_verify"] is False


def test_certificate_checking_can_be_turned_back_on(config_file):
    """Le laboratoire sert du HTTP en clair ; la production ne doit pas heriter
    de la tolerance qui allait avec."""
    cli.main(
        [
            "--config", str(config_file), "configure",
            "--server-url", "https://prod.cbc.cm", "--tls-verify",
        ]
    )
    assert _lire(config_file)["server"]["tls_verify"] is True


def test_an_address_without_a_scheme_is_refused(config_file):
    code = cli.main(["--config", str(config_file), "configure", "--server-url", "prod.cbc.cm"])

    assert code == 2
    # Rien n'est ecrit : un fichier a demi modifie laisserait l'agent muet.
    assert _lire(config_file)["server"]["url"] == "http://labo.local:8443"


def test_an_empty_address_is_refused(config_file):
    assert cli.main(["--config", str(config_file), "configure", "--server-url", "  "]) == 2


def test_a_missing_file_is_reported_rather_than_created(tmp_path):
    absent = tmp_path / "nulle-part.yaml"

    code = cli.main(["--config", str(absent), "configure", "--server-url", "https://prod.cbc.cm"])

    assert code == 2
    assert not absent.exists()


def test_a_broken_file_is_reported_without_being_overwritten(tmp_path):
    casse = tmp_path / "config.yaml"
    casse.write_text("server: [ceci n'est pas\n  du yaml valide: {", encoding="utf-8")

    code = cli.main(["--config", str(casse), "configure", "--server-url", "https://prod.cbc.cm"])

    assert code == 2
    assert "ceci n'est pas" in casse.read_text(encoding="utf-8")


def test_a_file_without_a_server_section_gains_one(tmp_path):
    """Une configuration minimale ne doit pas faire echouer la bascule."""
    minimal = tmp_path / "config.yaml"
    minimal.write_text(yaml.safe_dump({"agent": {"machine_type": "server"}}), encoding="utf-8")

    code = cli.main(["--config", str(minimal), "configure", "--server-url", "https://prod.cbc.cm"])

    assert code == 0
    assert _lire(minimal)["server"]["url"] == "https://prod.cbc.cm"
    assert _lire(minimal)["agent"]["machine_type"] == "server"


def test_the_enrolment_is_never_touched(config_file, monkeypatch):
    """Le point central : l'hote garde son identite et son historique."""
    efface = []
    monkeypatch.setattr(cli, "clear_credentials", lambda: efface.append(True))

    cli.main(["--config", str(config_file), "configure", "--server-url", "https://prod.cbc.cm"])

    assert efface == []


def test_no_temporary_file_is_left_behind(config_file):
    """L'ecriture est atomique ; le fichier intermediaire ne doit pas survivre."""
    cli.main(["--config", str(config_file), "configure", "--server-url", "https://prod.cbc.cm"])

    assert list(config_file.parent.glob("*.tmp")) == []


def test_moving_to_https_without_certificate_checking_is_flagged(config_file, capsys):
    """La tolerance du laboratoire ne doit pas survivre en silence a la bascule.

    La liaison serait chiffree mais n'attesterait plus l'identite de la
    plateforme, et rien ne le dirait.
    """
    cli.main(["--config", str(config_file), "configure", "--server-url", "https://prod.cbc.cm"])

    assert "certificat" in capsys.readouterr().err.lower()


def test_no_warning_when_the_certificate_is_checked(config_file, capsys):
    cli.main(
        [
            "--config", str(config_file), "configure",
            "--server-url", "https://prod.cbc.cm", "--tls-verify",
        ]
    )

    assert "Attention" not in capsys.readouterr().err


def test_no_warning_on_a_plain_http_laboratory(config_file, capsys):
    cli.main(["--config", str(config_file), "configure", "--server-url", "http://labo2.local:8443"])

    assert "Attention" not in capsys.readouterr().err
