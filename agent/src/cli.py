"""Point d'entrée de l'agent CBC Supervision.

Périmètre courant : enrôlement (point 1), désinstallation signalée (point 4),
battement et reprise de contact (point 5). Les verbes de collecte
paramétrable arriveront avec les points 6 et 7 ; ce fichier grandit avec eux
plutôt que d'annoncer aujourd'hui des commandes qui ne font rien.
"""

from __future__ import annotations

import argparse
import logging
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
from instance_lock import AlreadyRunning, InstanceLock
from runner import run as run_loop
from session import read_state

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


def cmd_run(args: argparse.Namespace) -> int:
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-8s %(message)s",
    )

    creds = read_credentials()
    if not creds:
        print(
            "Hôte non enrôlé — lancer « enroll » avant de battre.",
            file=sys.stderr,
        )
        return 2

    try:
        config = load_config(_config_path(args), url_override=args.server_url)
    except ConfigError as exc:
        print("Configuration : %s" % exc, file=sys.stderr)
        return 2

    host = collect(AGENT_VERSION, config)
    print(
        "Battement toutes les %ss vers %s (hôte %s)."
        % (args.interval, config.server_url, creds.agent_id)
    )

    # Un seul agent à la fois : deux boucles écriraient les mêmes fichiers
    # d'état, et l'une pourrait acquitter un plan que l'autre n'a pas rangé.
    try:
        lock = InstanceLock().acquire()
    except AlreadyRunning as exc:
        print("%s" % exc, file=sys.stderr)
        return 2

    try:
        outcome = run_loop(
            config,
            creds,
            host,
            interval_seconds=args.interval,
            max_beats=1 if args.once else None,
        )
    except KeyboardInterrupt:
        print()
        print("Arrêt demandé.")
        return 0
    finally:
        lock.release()

    if outcome.last_error and outcome.beats_sent == 0:
        print("Aucun battement accepté : %s" % outcome.last_error, file=sys.stderr)
        return 1
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    creds = read_credentials()
    print("Version agent : %s" % AGENT_VERSION)
    print("État local    : %s" % state_dir())
    # Vers quelle plateforme cet hôte parle : la première question posée
    # quand un agent « ne remonte pas », et celle à laquelle personne ne
    # pouvait répondre depuis la machine.
    path = _config_path(args)
    try:
        print("Plateforme    : %s" % load_config(path).server_url)
    except ConfigError as exc:
        print("Plateforme    : indéterminée (%s)" % exc)
    print("Configuration : %s" % (path or "aucun fichier"))
    print("Identité      : %s" % (machine_id_file() if machine_id_file().exists() else "non créée"))
    if creds:
        print("Enrôlement    : %s" % creds.agent_id)
    else:
        print("Enrôlement    : aucun — lancer « enroll »")

    # État de la liaison vu depuis l'hôte. C'est la réponse à « le parc
    # l'affiche hors ligne, qui a raison ? » — sans interroger la plateforme,
    # qui est justement ce qu'on met en doute.
    link = read_state()
    print("Liaison       : %s" % ("établie" if link.connected else "rompue"))
    print("Dernier succès: %s" % (link.last_success_at or "jamais"))
    if link.consecutive_failures:
        print("Échecs de suite: %d" % link.consecutive_failures)
    if link.last_error:
        print("Dernière erreur: %s" % link.last_error)
    return 0


def cmd_configure(args: argparse.Namespace) -> int:
    """Change l'adresse de la plateforme sans reenroler l'hote.

    Le passage du laboratoire a la production deplace la plateforme, pas les
    machines : desinstaller puis reinstaller le parc pour un changement
    d'adresse ferait perdre l'identite de chaque hote et son historique, et
    consommerait un jeton par poste. L'identite et les jetons sont donc
    conserves ; seule l'adresse change.
    """
    path = _config_path(args)
    if path is None:
        print(
            "Aucun fichier de configuration a modifier. Attendu : %s" % DEFAULT_CONFIG,
            file=sys.stderr,
        )
        return 2

    url = (args.server_url or "").strip()
    if not url.startswith(("http://", "https://")):
        print(
            "URL invalide : %r. Attendu une adresse commencant par http:// ou https://."
            % args.server_url,
            file=sys.stderr,
        )
        return 2

    try:
        import yaml

        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except FileNotFoundError:
        print("Fichier introuvable : %s" % path, file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001
        print("Configuration illisible (%s) : %s" % (path, exc), file=sys.stderr)
        return 2

    if not isinstance(raw, dict):
        print("Configuration inattendue dans %s." % path, file=sys.stderr)
        return 2

    server = raw.get("server")
    if not isinstance(server, dict):
        server = {}
    ancienne = server.get("url")
    server["url"] = url
    if args.tls_verify is not None:
        server["tls_verify"] = args.tls_verify
    raw["server"] = server

    # Ecriture atomique : une coupure au mauvais moment laisserait sinon un
    # fichier tronque, et l'agent ne saurait plus ou joindre la plateforme.
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(
            yaml.safe_dump(raw, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )
        tmp.replace(path)
    except OSError as exc:
        print("Ecriture impossible (%s) : %s" % (path, exc), file=sys.stderr)
        return 1

    print("Plateforme : %s -> %s" % (ancienne or "(non renseignee)", url))

    # Le laboratoire sert du HTTP en clair, et la configuration livree tolere
    # donc l'absence de certificat. Basculer en HTTPS sans revenir dessus
    # garderait cette tolerance : la liaison serait chiffree mais n'attesterait
    # plus l'identite de la plateforme -- une regression que rien ne signale.
    if url.startswith("https://") and server.get("tls_verify") is False:
        print(
            "Attention : le certificat de la plateforme n'est pas verifie. "
            "La liaison est chiffree, mais un autre serveur pourrait se faire "
            "passer pour elle. Relancer avec --tls-verify une fois le "
            "certificat en place.",
            file=sys.stderr,
        )
    if is_enrolled():
        creds = read_credentials()
        print("Hote %s conserve : ni reenrolement ni perte d'historique." % creds.agent_id)
        print("Redemarrer le service pour que le changement prenne effet.")
    else:
        print("Hote non enrole : lancer « enroll » avec un jeton.")
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

    run_cmd = sub.add_parser("run", help="bat vers la plateforme jusqu'à interruption")
    run_cmd.add_argument("--server-url", help="URL de la plateforme")
    run_cmd.add_argument(
        "--interval", type=float, default=30.0, help="secondes entre deux battements"
    )
    run_cmd.add_argument("--once", action="store_true", help="un seul battement puis sortie")
    run_cmd.add_argument("--verbose", action="store_true", help="journal détaillé")
    run_cmd.set_defaults(func=cmd_run)

    configure_cmd = sub.add_parser(
        "configure",
        help="change l'adresse de la plateforme sans réenrôler",
    )
    configure_cmd.add_argument(
        "--server-url", required=True, help="nouvelle URL de la plateforme"
    )
    configure_cmd.add_argument(
        "--tls-verify",
        dest="tls_verify",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="vérifier le certificat de la plateforme",
    )
    configure_cmd.set_defaults(func=cmd_configure)

    status_cmd = sub.add_parser("status", help="état local de l'agent")
    status_cmd.set_defaults(func=cmd_status)
    sub.add_parser("version", help="version de l'agent").set_defaults(func=cmd_version)
    return parser


def _force_utf8_output() -> None:
    """Ecrit en UTF-8, quelle que soit la console.

    Sous Windows, Python choisit l'encodage local (cp1252) des que sa sortie
    est redirigee — ce que fait l'installateur. « Hote » arrivait alors comme
    « H¶te » dans les messages de diagnostic, et l'exploitant se met a
    douter du binaire au lieu de lire ce qu'on lui dit.
    """
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            # Flux exotique ou deja consomme : mieux vaut un accent abime
            # qu'un agent qui refuse de demarrer.
            pass


def main(argv: list[str] | None = None) -> int:
    _force_utf8_output()
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 2
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
