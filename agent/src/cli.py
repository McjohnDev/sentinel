"""Point d'entrée de l'agent CBC Supervision.

Périmètre courant : point 1 — enrôlement. Les verbes de collecte et de
heartbeat arriveront avec les points suivants ; ce fichier grandit avec eux
plutôt que d'annoncer aujourd'hui des commandes qui ne font rien.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from agent_paths import credentials_file, machine_id_file, state_dir
from config import ConfigError, load_config
from enrollment import (
    AGENT_VERSION,
    DeregistrationError,
    EnrollmentError,
    clear_credentials,
    deregister,
    enroll,
    is_enrolled,
    read_credentials,
)
from facts import collect
from identity import load_or_create_machine_id

DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "config.yaml"


def _config_path(args: argparse.Namespace) -> Path | None:
    if args.config:
        return Path(args.config)
    return DEFAULT_CONFIG if DEFAULT_CONFIG.exists() else None


def cmd_enroll(args: argparse.Namespace) -> int:
    try:
        config = load_config(
            _config_path(args),
            token_override=args.token,
            url_override=args.server_url,
        )
    except ConfigError as exc:
        print("Configuration : %s" % exc, file=sys.stderr)
        return 2

    if is_enrolled() and not args.force:
        creds = read_credentials()
        print("Hôte déjà enrôlé sous l'identifiant %s." % creds.agent_id)
        print("Relancer avec --force pour réenrôler (consomme un nouveau jeton).")
        return 0

    # Contrôlé avant de relever quoi que ce soit : sans jeton la commande ne
    # peut pas aboutir, et annoncer l'hôte puis échouer laisse croire que
    # l'enrôlement a commencé.
    if not config.enrollment_token:
        print(
            "Aucun jeton d'enrôlement. Le fournir par --token, la variable "
            "CBC_ENROLLMENT_TOKEN, ou server.enrollment_token.",
            file=sys.stderr,
        )
        return 2

    machine_id = load_or_create_machine_id()
    host = collect(AGENT_VERSION)

    print("Hôte      : %s (%s %s)" % (host.hostname, host.os, host.os_version))
    print("Machine   : %s" % machine_id)
    print("Plateforme: %s" % config.enroll_url)

    try:
        creds = enroll(config, machine_id, host)
    except EnrollmentError as exc:
        print("Échec : %s" % exc, file=sys.stderr)
        return 1

    print()
    print("Enrôlé. Identifiant attribué par la plateforme : %s" % creds.agent_id)
    print("Jetons conservés dans %s" % credentials_file())
    return 0


def cmd_uninstall(args: argparse.Namespace) -> int:
    creds = read_credentials()
    if not creds:
        print("Cet hôte n'est pas enrôlé — rien à signaler.")
        return 0

    try:
        config = load_config(_config_path(args), url_override=args.server_url)
    except ConfigError as exc:
        print("Configuration : %s" % exc, file=sys.stderr)
        return 2

    try:
        deregister(config, creds, reason=args.reason)
    except DeregistrationError as exc:
        # Par défaut on refuse d'effacer les jetons sans avoir prévenu la
        # plateforme : sinon l'hôte disparaît sans un mot et reste affiché
        # « hors ligne » au parc, indistinguable d'une panne. L'exploitant
        # doit pouvoir forcer — une machine mise au rebut ne rejoindra jamais
        # le réseau — mais en le sachant.
        print("Échec du signalement : %s" % exc, file=sys.stderr)
        if not args.force:
            print(
                "Jetons conservés. Relancer quand la plateforme répond, ou "
                "--force pour désinstaller sans la prévenir (l'hôte restera "
                "affiché hors ligne jusqu'à son retrait manuel).",
                file=sys.stderr,
            )
            return 1
        clear_credentials()
        print("Jetons effacés sans signalement (--force).")
        return 1

    clear_credentials()
    print("Désenrôlement signalé — hôte %s marqué désinstallé." % creds.agent_id)
    print("L'identité machine est conservée : une réinstallation retrouvera")
    print("le même hôte et son historique.")
    return 0


def cmd_status(_args: argparse.Namespace) -> int:
    creds = read_credentials()
    print("Version agent : %s" % AGENT_VERSION)
    print("État local    : %s" % state_dir())
    print("Identité      : %s" % (machine_id_file() if machine_id_file().exists() else "non créée"))
    if creds:
        print("Enrôlement    : %s" % creds.agent_id)
    else:
        print("Enrôlement    : aucun — lancer « enroll »")
    return 0


def cmd_version(_args: argparse.Namespace) -> int:
    print(AGENT_VERSION)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cbc-agent",
        description="Agent de supervision CBC.",
    )
    parser.add_argument("--config", help="chemin du fichier de configuration")
    sub = parser.add_subparsers(dest="command")

    enroll_cmd = sub.add_parser("enroll", help="enrôle cet hôte auprès de la plateforme")
    enroll_cmd.add_argument("--token", help="jeton d'enrôlement à usage unique")
    enroll_cmd.add_argument("--server-url", help="URL de la plateforme")
    enroll_cmd.add_argument(
        "--force",
        action="store_true",
        help="réenrôle un hôte déjà enrôlé (consomme un nouveau jeton)",
    )
    enroll_cmd.set_defaults(func=cmd_enroll)

    uninstall_cmd = sub.add_parser(
        "uninstall", help="signale la désinstallation puis oublie les jetons"
    )
    uninstall_cmd.add_argument("--reason", help="motif transmis à la plateforme")
    uninstall_cmd.add_argument("--server-url", help="URL de la plateforme")
    uninstall_cmd.add_argument(
        "--force",
        action="store_true",
        help="désinstalle même si la plateforme ne peut pas être prévenue",
    )
    uninstall_cmd.set_defaults(func=cmd_uninstall)

    sub.add_parser("status", help="état local de l'agent").set_defaults(func=cmd_status)
    sub.add_parser("version", help="version de l'agent").set_defaults(func=cmd_version)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 2
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
