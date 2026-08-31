"""Interface en ligne de commande de l'agent CBC.

Motivation — le défaut le plus grave du paquet actuel : l'agent n'analysait
pas ses arguments. Il testait `sys.argv[1].endswith('.yaml')`, alors que
*tous* les services installés (systemd, launchd, MSI, `install.sh`) le lancent
avec `--config /etc/cbc-agent/config.yaml`. Résultat : `--config` était pris
pour une URL de serveur et le chemin du fichier pour un jeton d'enrôlement.
**Aucun agent installé hors Docker ne chargeait sa configuration.**

Cette CLI corrige cela et fournit les verbes qui manquaient à l'exploitation :

    cbc-agent run [--config PATH]     supervision (comportement par défaut)
    cbc-agent enroll --token TOKEN    enrôlement seul, sans démarrer la boucle
    cbc-agent uninstall               désenrôlement + nettoyage local
    cbc-agent status                  état de liaison, vu depuis l'hôte
    cbc-agent validate-config         vérification du fichier avant démarrage
    cbc-agent version

La forme historique (`agent.py /chemin/config.yaml`) reste acceptée : l'image
Docker s'en sert, et casser un déploiement qui fonctionne pour faire propre
serait un mauvais échange.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from agent_paths import machine_id_path, resolve_buffer_dir

DEFAULT_BUFFER_DIR = "data/agent-buffer"

#: Verbes reconnus. Sert aussi à distinguer une sous-commande d'un argument
#: hérité de l'ancienne forme positionnelle.
_SUBCOMMANDS = frozenset(
    {"run", "enroll", "uninstall", "status", "validate-config", "version"}
)

#: Emplacements standards, par ordre de préférence, quand `--config` est absent.
_CONFIG_SEARCH_PATHS = {
    "win32": [r"C:\Program Files\CBC Agent\config.yaml"],
    "darwin": ["/etc/cbc-agent/config.yaml"],
    "linux": ["/etc/cbc-agent/config.yaml"],
}


# --------------------------------------------------------------- utilitaires


def _agent_version() -> str:
    try:
        from agent import CBCAgent  # type: ignore[import-not-found]

        return CBCAgent._get_agent_version(None)  # type: ignore[arg-type]
    except Exception:
        return "1.1.0"


def resolve_config_path(explicit: Optional[str]) -> Optional[str]:
    """Chemin du fichier de configuration réellement retenu.

    Ordre : `--config`, puis `CBC_AGENT_CONFIG`, puis l'emplacement standard
    du système, puis `config.yaml` à côté du paquet.
    """
    if explicit:
        return explicit
    env = os.environ.get("CBC_AGENT_CONFIG")
    if env:
        return env
    for candidate in _CONFIG_SEARCH_PATHS.get(sys.platform, ["/etc/cbc-agent/config.yaml"]):
        if Path(candidate).is_file():
            return candidate
    local = Path(__file__).resolve().parent.parent / "config.yaml"
    return str(local) if local.is_file() else None


def load_config(path: Optional[str]) -> Dict[str, Any]:
    """Lecture tolérante : un fichier absent ou vide donne un dict vide.

    `yaml.safe_load` renvoie `None` sur un fichier vide — le convertir ici
    évite un `AttributeError` chez chaque appelant.
    """
    if not path or not Path(path).is_file():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, yaml.YAMLError):
        return {}


def buffer_dir_from(config: Dict[str, Any], config_path: Optional[str] = None) -> Path:
    """Même ancrage que l'agent — sinon la CLI lirait un autre tampon que lui."""
    degraded = config.get("degraded_mode") or {}
    return resolve_buffer_dir(degraded.get("buffer_dir") or DEFAULT_BUFFER_DIR, config_path)


def load_session(config: Dict[str, Any], config_path: Optional[str] = None) -> Dict[str, Any]:
    """Dernier état connu de la liaison (identifiant, clé, dernière erreur)."""
    path = buffer_dir_from(config, config_path) / "session.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def server_url_from(config: Dict[str, Any], session: Dict[str, Any]) -> Optional[str]:
    return (config.get("server") or {}).get("url") or session.get("server_url")


# ------------------------------------------------------------ validate-config


def validate_config(
    config: Dict[str, Any], path: Optional[str]
) -> Tuple[bool, List[str], List[str]]:
    """Vérifie la configuration, en séparant ce qui bloque de ce qui alerte.

    La distinction est délibérée. Un contrôle qui refuse de démarrer sur une
    imperfection non bloquante immobilise une supervision qui aurait
    fonctionné — le remède est alors pire que le mal. Ne bloquent donc que
    les défauts qui rendent l'agent réellement inopérant ; le reste remonte
    en avertissement, visible mais non paralysant.

    Renvoie `(exploitable, bloquants, avertissements)`.
    """
    blocking: List[str] = []
    warnings: List[str] = []

    if path is None:
        blocking.append(
            "Aucun fichier de configuration trouvé. Passez --config CHEMIN "
            "ou définissez CBC_AGENT_CONFIG."
        )
        return False, blocking, warnings

    if not config:
        blocking.append(f"{path} est vide ou illisible.")
        return False, blocking, warnings

    server = config.get("server") or {}
    url = server.get("url")
    if not url:
        blocking.append("server.url est absent : l'agent ne sait pas où émettre.")
    elif not str(url).startswith(("http://", "https://")):
        blocking.append(f"server.url doit commencer par http:// ou https:// (reçu : {url!r}).")
    elif str(url).startswith("http://"):
        # Non bloquant : `tls_verify` n'a simplement pas d'objet sans TLS, et
        # les piles de laboratoire tournent légitimement en clair. Le risque
        # — identifiants d'agent circulant sans chiffrement — doit néanmoins
        # se voir.
        warnings.append(
            "server.url est en clair (http://) : les identifiants de l'agent "
            "circulent sans chiffrement. Acceptable en laboratoire, à proscrire en production."
        )

    if str(url or "").startswith("https://") and server.get("tls_verify", True) is False:
        warnings.append(
            "tls_verify est désactivé sur une liaison https:// : le certificat "
            "du serveur n'est pas vérifié, l'interception reste possible."
        )

    # Le jeton vide est le piège classique : la clé *existe* dans le YAML
    # livré, donc le repli par défaut ne s'applique jamais et l'enrôlement
    # boucle sans message distinctif. Non bloquant pour autant : un agent
    # déjà enrôlé n'a plus besoin de jeton et doit continuer à tourner.
    if "enrollment_token" in server and not str(server.get("enrollment_token") or "").strip():
        warnings.append(
            "server.enrollment_token est présent mais vide. Sans jeton, un "
            "agent pas encore enrôlé bouclera sans jamais aboutir. Renseignez "
            "un jeton émis depuis Parametres > Agents, ou retirez la clé."
        )

    agent_cfg = config.get("agent") or {}
    machine_type = agent_cfg.get("machine_type", "workstation")
    if machine_type not in ("server", "workstation"):
        blocking.append(
            f"agent.machine_type doit valoir 'server' ou 'workstation' (reçu : {machine_type!r})."
        )

    for key in ("heartbeat_interval", "ping_interval"):
        value = agent_cfg.get(key)
        if value is not None and (not isinstance(value, int) or value < 1):
            blocking.append(f"agent.{key} doit être un entier positif (reçu : {value!r}).")

    return not blocking, blocking, warnings


# ----------------------------------------------------------------- désinstall


#: `sc stop` sur un service inexistant. Ce n'est pas une erreur pendant une
#: désinstallation : il n'y a simplement rien à arrêter.
_WIN_SERVICE_ABSENT = 1060


def _stop_service() -> Tuple[bool, str]:
    """Arrête le service s'il y en a un, et **dit ce qui s'est réellement passé**.

    La version précédente lançait la commande sans regarder son code de
    retour et annonçait « service arrêté » dans tous les cas — y compris
    lorsque aucun service n'était installé. Un message de succès pour une
    action qui n'a pas eu lieu est pire que pas de message : il fait croire
    l'hôte propre alors qu'un agent peut encore tourner.

    Le retrait définitif reste au gestionnaire de paquets (dpkg, rpm,
    msiexec) ; ici on s'assure seulement que le processus cesse d'émettre
    avant d'effacer ses identifiants.
    """
    try:
        if sys.platform == "win32":
            done = subprocess.run(["sc", "stop", "CBCAgent"], capture_output=True, timeout=30)
            if done.returncode == 0:
                return True, "Service Windows CBCAgent arrêté (retrait par le désinstalleur MSI)."
            if done.returncode == _WIN_SERVICE_ABSENT:
                return True, "Aucun service CBCAgent installé — rien à arrêter."
            detail = (done.stdout or b"").decode(errors="replace").strip().splitlines()
            return False, (
                f"Arrêt du service CBCAgent refusé (code {done.returncode})"
                + (f" : {detail[-1].strip()}" if detail else "")
                + ". Droits administrateur requis ?"
            )

        if sys.platform == "darwin":
            plist = "/Library/LaunchDaemons/com.cbc.agent.plist"
            if not Path(plist).exists():
                return True, "Aucun démon launchd installé — rien à décharger."
            done = subprocess.run(["launchctl", "unload", plist], capture_output=True, timeout=30)
            if done.returncode == 0:
                return True, "Démon launchd déchargé."
            return False, f"Déchargement launchd refusé (code {done.returncode})."

        if shutil.which("systemctl"):
            present = subprocess.run(
                ["systemctl", "list-unit-files", "cbc-agent.service"],
                capture_output=True,
                timeout=30,
            )
            if b"cbc-agent.service" not in (present.stdout or b""):
                return True, "Aucune unité systemd cbc-agent — rien à arrêter."
            stopped = subprocess.run(["systemctl", "stop", "cbc-agent"], capture_output=True, timeout=30)
            subprocess.run(["systemctl", "disable", "cbc-agent"], capture_output=True, timeout=30)
            if stopped.returncode == 0:
                return True, "Unité systemd cbc-agent arrêtée et désactivée."
            return False, f"Arrêt systemd refusé (code {stopped.returncode}). Droits root requis ?"

        return False, "Aucun gestionnaire de service reconnu — arrêt manuel nécessaire."
    except (subprocess.SubprocessError, OSError) as exc:
        return False, f"Arrêt du service impossible : {exc}"


def _purge_local_state(config: Dict[str, Any], config_path: Optional[str] = None) -> List[str]:
    """Efface identifiants et files d'attente locales.

    La clé d'authentification est stockée en clair dans `session.json` : la
    laisser sur un poste désinstallé serait un identifiant abandonné.
    """
    removed: List[str] = []
    buffer_dir = buffer_dir_from(config, config_path)
    for target in (
        buffer_dir / "session.json",
        buffer_dir / "queue.jsonl",
        buffer_dir / "remote-config.yaml",
        buffer_dir / "remote-config.meta.json",
        # Résolu comme l'agent le résout, variable d'environnement comprise :
        # le coder en dur ici effaçait un fichier sans rapport sous Docker et
        # laissait le véritable identifiant dans son volume.
        machine_id_path(),
    ):
        try:
            if target.exists():
                target.unlink()
                removed.append(str(target))
        except OSError:
            pass

    try:
        from instance_lock import InstanceLock

        lock_path = InstanceLock().path
        if lock_path.exists():
            lock_path.unlink()
            removed.append(str(lock_path))
    except Exception:
        pass

    return removed


def cmd_uninstall(args: argparse.Namespace) -> int:
    """Signale le désenrôlement à la plateforme, puis nettoie l'hôte.

    L'ordre compte : on prévient d'abord, on efface ensuite. L'inverse
    perdrait la clé nécessaire pour se faire reconnaître, et l'hôte
    resterait dans l'inventaire jusqu'à la purge d'ancienneté — c'est-à-dire
    affiché comme supervisé alors qu'il ne l'est plus.
    """
    import requests

    config_path = resolve_config_path(args.config)
    config = load_config(config_path)
    session = load_session(config, config_path)

    auth_key = session.get("auth_key")
    agent_id = session.get("agent_id")
    server_url = server_url_from(config, session)
    tls_verify = (config.get("server") or {}).get("tls_verify", True)

    print(f"Configuration : {config_path or '(aucune)'}")
    print(f"Agent         : {agent_id or '(non enrôlé)'}")
    print(f"Plateforme    : {server_url or '(inconnue)'}")
    print()

    deregistered = False
    if auth_key and server_url:
        try:
            response = requests.post(
                f"{server_url}/api/agents/deregister",
                json={"reason": args.reason} if args.reason else {},
                headers={"Authorization": auth_key},
                timeout=15,
                verify=tls_verify,
            )
            if 200 <= response.status_code < 300:
                print("[ok] Désenrôlement signalé à la plateforme.")
                deregistered = True
            elif response.status_code in (401, 403, 404):
                # La plateforme ne connaît plus cette identité : le but est
                # déjà atteint, ce n'est pas une erreur de désinstallation.
                print("[ok] La plateforme ne connaissait plus cet agent — rien à signaler.")
                deregistered = True
            else:
                print(f"[!] Réponse inattendue : HTTP {response.status_code} {response.text[:200]}")
        except requests.RequestException as exc:
            print(f"[!] Plateforme injoignable : {exc}")
            print("    L'hôte restera affiché jusqu'à la purge d'inventaire.")
    else:
        print("[i] Aucune session locale : rien à signaler à la plateforme.")
        deregistered = True

    ok, message = _stop_service()
    print(f"[{'ok' if ok else '!'}] {message}")

    if args.keep_data:
        print("[i] État local conservé (--keep-data).")
    else:
        removed = _purge_local_state(config, config_path)
        print(f"[ok] État local effacé ({len(removed)} fichier(s)).")
        for item in removed:
            print(f"     - {item}")

    print()
    if deregistered:
        print("Désinstallation terminée.")
        return 0
    print("Désinstallation locale terminée, mais la plateforme n'a pas été prévenue.")
    return 2


# --------------------------------------------------------------------- status


def running_agent() -> Optional[Dict[str, Any]]:
    """Décrit l'agent réellement en service, s'il y en a un.

    `status` décrivait jusqu'ici *son propre* processus : il affichait donc
    son PID, sa durée de vie et son mode d'exécution — pas ceux de l'agent.
    Sur un poste où l'agent tourne depuis des heures, le diagnostic annonçait
    « actif depuis 0 minute », ce qui est faux et trompeur au moment précis où
    l'on cherche à savoir depuis quand il tourne.

    Le verrou d'instance fait autorité : c'est l'agent lui-même qui y inscrit
    son PID.
    """
    from instance_lock import InstanceLock

    lock = InstanceLock()
    if not lock.path.exists():
        return None
    try:
        pid = int(lock.path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None

    try:
        import psutil

        proc = psutil.Process(pid)
        with proc.oneshot():
            return {
                "pid": pid,
                "started_at": datetime.fromtimestamp(
                    proc.create_time(), tz=timezone.utc
                ).isoformat(),
                "uptime_seconds": max(0, int(time.time() - proc.create_time())),
                "memory_mb": round(proc.memory_info().rss / (1024 * 1024), 1),
                "run_as_user": proc.username(),
                "executable": proc.exe(),
            }
    except Exception:
        # Verrou présent mais processus disparu : un agent tué brutalement.
        return {"pid": pid, "stale": True}


def cmd_status(args: argparse.Namespace) -> int:
    """État de la liaison, tel que l'hôte le voit — sans interroger le serveur."""
    from runtime_info import collect_runtime_info

    config_path = resolve_config_path(args.config)
    config = load_config(config_path)
    session = load_session(config, config_path)
    live = running_agent()

    runtime = collect_runtime_info(
        config_path=config_path,
        server_url=server_url_from(config, session),
        tls_verify=(config.get("server") or {}).get("tls_verify", True),
        agent_version=_agent_version(),
        buffer_records=session.get("buffer_records"),
        last_error=session.get("last_error"),
    )

    if args.json:
        print(
            json.dumps(
                {"running": live, "runtime": runtime, "session": session},
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0

    connected = session.get("connected")
    print("=== Agent CBC Supervision ===")
    if live is None:
        print("  Processus        : arrêté")
    elif live.get("stale"):
        print(f"  Processus        : verrou orphelin (PID {live['pid']} disparu)")
    else:
        hours, rem = divmod(live["uptime_seconds"], 3600)
        print(
            f"  Processus        : en service, PID {live['pid']}, "
            f"depuis {hours}h{rem // 60:02d}, {live['memory_mb']} Mo"
        )
    print(f"  Identifiant      : {session.get('agent_id') or '(non enrôlé)'}")
    print(f"  Liaison          : {'connecté' if connected else 'hors ligne'}")
    print(f"  Dernier succès   : {session.get('last_success_at') or '—'}")
    print(f"  Dernière erreur  : {session.get('last_error') or '—'}")
    print(f"  Échecs consécut. : {session.get('consecutive_failures', 0)}")
    print(f"  En tampon        : {session.get('buffer_records', 0)} enregistrement(s)")
    print()
    # Ce bloc décrit l'installation — chemins, packaging, liaison — et non le
    # processus courant : le PID et la durée de vie de l'agent en service sont
    # donnés ci-dessus, à partir du verrou.
    print("=== Installation sur l'hôte ===")
    print(f"  Mode             : {runtime['run_mode']}" + (f" ({runtime['service_name']})" if runtime["service_name"] else ""))
    print(f"  Compte           : {live.get('run_as_user') if live and not live.get('stale') else runtime['run_as_user']}" + (" (élevé)" if runtime["elevated"] else ""))
    print(f"  Exécutable       : {runtime['executable_path']}")
    print(f"  Installation     : {runtime['install_dir']}")
    print(f"  Configuration    : {runtime['config_path'] or '(aucune)'}")
    print(f"  Packaging        : {runtime['packaging']}")
    print(f"  Plateforme       : {runtime['server_url'] or '(inconnue)'}  TLS={runtime['tls_verify']}")

    ok, blocking, warnings = validate_config(config, config_path)
    if blocking or warnings:
        print()
        print("=== Configuration ===")
        for problem in blocking:
            print(f"  [BLOQUANT]  {problem}")
        for warning in warnings:
            print(f"  [attention] {warning}")
    return 0 if ok else 1


def cmd_validate(args: argparse.Namespace) -> int:
    config_path = resolve_config_path(args.config)
    config = load_config(config_path)
    ok, blocking, warnings = validate_config(config, config_path)
    print(f"Fichier : {config_path or '(aucun)'}")
    for problem in blocking:
        print(f"[BLOQUANT] {problem}")
    for warning in warnings:
        print(f"[attention] {warning}")
    if ok:
        print("[ok] Configuration exploitable." + (" Avertissements ci-dessus." if warnings else ""))
        return 0
    return 1


def cmd_version(_args: argparse.Namespace) -> int:
    print(f"cbc-agent {_agent_version()}")
    return 0


# ------------------------------------------------------------------ run/enroll


def _build_agent(args: argparse.Namespace):
    from agent import CBCAgent  # import différé : démarre plugins et journalisation

    return CBCAgent(
        config_path=resolve_config_path(args.config),
        server_url=getattr(args, "server", None),
        enrollment_token=getattr(args, "token", None),
    )


def cmd_run(args: argparse.Namespace) -> int:
    from instance_lock import InstanceLock, InstanceLockError

    config_path = resolve_config_path(args.config)
    config = load_config(config_path)
    ok, blocking, warnings = validate_config(config, config_path)
    for warning in warnings:
        print(f"[attention] {warning}", file=sys.stderr)
    if not ok and not args.force:
        print("Configuration inexploitable — démarrage refusé :", file=sys.stderr)
        for problem in blocking:
            print(f"  [BLOQUANT] {problem}", file=sys.stderr)
        print("  (--force pour démarrer malgré tout)", file=sys.stderr)
        return 1

    lock = InstanceLock()
    try:
        lock.acquire()
    except InstanceLockError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    try:
        _build_agent(args).run()
    finally:
        lock.release()
    return 0


def cmd_enroll(args: argparse.Namespace) -> int:
    """Enrôle sans démarrer la boucle — utile pour valider un jeton à l'installation."""
    agent = _build_agent(args)
    if agent.enroll():
        print(f"[ok] Agent enrôlé. Identifiant attribué : {agent.agent_id}")
        return 0
    print("[!] Enrôlement refusé. Vérifiez le jeton et l'accès à la plateforme.", file=sys.stderr)
    return 1


# ------------------------------------------------------------------ analyseur


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cbc-agent",
        description="Agent de supervision CBC.",
    )
    parser.add_argument("--version", action="store_true", help="affiche la version et quitte")
    sub = parser.add_subparsers(dest="command")

    def with_config(p: argparse.ArgumentParser) -> argparse.ArgumentParser:
        p.add_argument("--config", "-c", metavar="CHEMIN", help="fichier de configuration YAML")
        return p

    run = with_config(sub.add_parser("run", help="démarre la supervision (défaut)"))
    run.add_argument("--server", metavar="URL", help="surcharge server.url")
    run.add_argument("--token", metavar="JETON", help="surcharge le jeton d'enrôlement")
    run.add_argument("--force", action="store_true", help="démarre malgré une configuration invalide")
    run.set_defaults(func=cmd_run)

    enroll = with_config(sub.add_parser("enroll", help="enrôle l'agent puis quitte"))
    enroll.add_argument("--server", metavar="URL", help="surcharge server.url")
    enroll.add_argument("--token", metavar="JETON", required=False, help="jeton d'enrôlement")
    enroll.set_defaults(func=cmd_enroll)

    uninstall = with_config(sub.add_parser("uninstall", help="désenrôle et nettoie l'hôte"))
    uninstall.add_argument("--keep-data", action="store_true", help="conserve l'état local")
    uninstall.add_argument("--reason", metavar="TEXTE", help="motif transmis à la plateforme")
    uninstall.set_defaults(func=cmd_uninstall)

    status = with_config(sub.add_parser("status", help="état de la liaison vu depuis l'hôte"))
    status.add_argument("--json", action="store_true", help="sortie machine")
    status.set_defaults(func=cmd_status)

    validate = with_config(sub.add_parser("validate-config", help="vérifie le fichier de configuration"))
    validate.set_defaults(func=cmd_validate)

    version = sub.add_parser("version", help="affiche la version")
    version.set_defaults(func=cmd_version)

    return parser


def _legacy_argv(argv: List[str]) -> Optional[List[str]]:
    """Traduit l'ancienne forme positionnelle vers la nouvelle.

    Historiquement : `agent.py <config.yaml>` ou `agent.py <url> [jeton]`.
    L'image Docker utilise encore la première — la rejeter casserait un
    déploiement qui fonctionne.
    """
    if not argv:
        return None
    first = argv[0]
    if first in _SUBCOMMANDS:
        return None
    if first.startswith("-"):
        # `cbc-agent --config /etc/cbc-agent/config.yaml` : c'est exactement
        # la ligne ExecStart de tous les services packagés. Sans sous-commande
        # explicite, l'intention est de superviser.
        if first in ("-h", "--help", "--version"):
            return None
        return ["run"] + argv
    if first.endswith((".yaml", ".yml")):
        return ["run", "--config", first]
    if first.startswith(("http://", "https://")):
        translated = ["run", "--server", first]
        if len(argv) > 1:
            translated += ["--token", argv[1]]
        return translated
    return None


def _configure_console() -> None:
    """Rend la sortie lisible sur une console Windows en page de code héritée.

    `cmd.exe` reste en cp1252 par défaut : la moindre lettre accentuée — donc
    la quasi-totalité des messages de cet agent — faisait tomber la commande
    sur un `UnicodeEncodeError`. Un outil de diagnostic qui plante en
    affichant son diagnostic est pire qu'inutile.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, ValueError, OSError):
            # Flux redirigé ou déjà encapsulé : on n'insiste pas.
            pass


def main(argv: Optional[List[str]] = None) -> int:
    _configure_console()
    argv = list(sys.argv[1:] if argv is None else argv)

    legacy = _legacy_argv(argv)
    if legacy is not None:
        argv = legacy

    parser = build_parser()
    args = parser.parse_args(argv)

    if getattr(args, "version", False) and not getattr(args, "command", None):
        return cmd_version(args)

    if not getattr(args, "func", None):
        # Sans sous-commande : superviser. C'est ce qu'attend un service.
        args = parser.parse_args(["run"])

    return args.func(args)
