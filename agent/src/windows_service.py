"""Exécution de l'agent en tant que service Windows.

**Le défaut corrigé.** L'exécutable produit par PyInstaller était une simple
application console (`console=True`, aucun gestionnaire SCM), alors que le
paquet MSI et `install.sh` l'enregistraient directement comme service via
`ServiceInstall` / `sc create`. Windows attend d'un binaire de service qu'il
se déclare auprès du gestionnaire de services dans les secondes qui suivent
son lancement ; faute de quoi il échoue avec l'erreur 1053, « le service n'a
pas répondu assez vite ». **Aucune installation Windows ne pouvait donc
fonctionner en service.**

Ce module fournit le point d'entrée qui manquait. Il ne réimplémente rien de
la supervision : il enveloppe `CBCAgent.run()` dans le protocole attendu par
le gestionnaire de services.

Deux exigences dictent sa forme :

* **Répondre vite au démarrage.** La construction de l'agent (chargement des
  plugins, du collecteur de journaux) prend un temps variable. On se déclare
  donc « démarré » d'abord, et on construit ensuite, dans un fil dédié.
* **S'arrêter proprement.** `SvcStop` demande l'arrêt et attend la fin de la
  boucle, plutôt que de laisser Windows tuer le processus — un tampon en
  cours d'écriture serait tronqué.
"""

from __future__ import annotations

import sys
import threading
from pathlib import Path

try:
    import servicemanager
    import win32event
    import win32service
    import win32serviceutil

    PYWIN32_AVAILABLE = True
except ImportError:  # pragma: no cover — module utile seulement sous Windows
    PYWIN32_AVAILABLE = False
    win32serviceutil = None  # type: ignore[assignment]

#: Nom court du service, tel que `sc` et `services.msc` le connaissent.
SERVICE_NAME = "CBCAgent"
SERVICE_DISPLAY_NAME = "CBC Supervision — Agent"
SERVICE_DESCRIPTION = (
    "Collecte les métriques système et remonte l'état de cet hôte à la "
    "plateforme de supervision CBC."
)

#: Délai laissé à la boucle pour se terminer d'elle-même après une demande
#: d'arrêt. Au-delà, Windows reprend la main. Large par rapport au tour de
#: boucle (1 s), mais en deçà du délai par défaut du gestionnaire (30 s).
STOP_TIMEOUT_SECONDS = 20


if PYWIN32_AVAILABLE:

    class CBCAgentService(win32serviceutil.ServiceFramework):
        """Adaptateur entre le gestionnaire de services et la boucle de l'agent."""

        _svc_name_ = SERVICE_NAME
        _svc_display_name_ = SERVICE_DISPLAY_NAME
        _svc_description_ = SERVICE_DESCRIPTION

        def __init__(self, args):
            super().__init__(args)
            # Évènement propre au SCM, distinct de celui de l'agent : il sert
            # à réveiller le fil principal pendant qu'il attend la fin.
            self._wake = win32event.CreateEvent(None, 0, 0, None)
            self._agent = None
            self._worker: threading.Thread | None = None

        # ------------------------------------------------------------ arrêt

        def SvcStop(self):
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            servicemanager.LogInfoMsg(f"{SERVICE_NAME} : arrêt demandé")
            if self._agent is not None:
                self._agent.request_stop()
            win32event.SetEvent(self._wake)

        # --------------------------------------------------------- démarrage

        def SvcDoRun(self):
            # Déclaré démarré avant toute construction coûteuse : le
            # gestionnaire n'attend pas le chargement des plugins.
            self.ReportServiceStatus(win32service.SERVICE_RUNNING)
            servicemanager.LogInfoMsg(f"{SERVICE_NAME} : démarrage")

            self._worker = threading.Thread(target=self._run_agent, name="cbc-agent", daemon=True)
            self._worker.start()

            win32event.WaitForSingleObject(self._wake, win32event.INFINITE)

            if self._worker.is_alive():
                self._worker.join(timeout=STOP_TIMEOUT_SECONDS)
                if self._worker.is_alive():
                    servicemanager.LogWarningMsg(
                        f"{SERVICE_NAME} : la boucle ne s'est pas terminée en "
                        f"{STOP_TIMEOUT_SECONDS}s, arrêt forcé"
                    )
            servicemanager.LogInfoMsg(f"{SERVICE_NAME} : arrêté")

        # ---------------------------------------------------------- travail

        def _run_agent(self):
            """Construit puis fait tourner l'agent, dans le fil dédié."""
            try:
                _ensure_import_path()
                from cli import resolve_config_path
                from instance_lock import InstanceLock, InstanceLockError

                config_path = resolve_config_path(None)
                if config_path is None:
                    servicemanager.LogErrorMsg(
                        f"{SERVICE_NAME} : aucune configuration trouvée. "
                        "Définissez CBC_AGENT_CONFIG ou placez config.yaml "
                        "dans le répertoire d'installation."
                    )
                    self.SvcStop()
                    return

                lock = InstanceLock()
                try:
                    lock.acquire()
                except InstanceLockError as exc:
                    servicemanager.LogErrorMsg(f"{SERVICE_NAME} : {exc}")
                    self.SvcStop()
                    return

                try:
                    from agent import CBCAgent

                    self._agent = CBCAgent(config_path=config_path)
                    servicemanager.LogInfoMsg(
                        f"{SERVICE_NAME} : configuration {config_path}"
                    )
                    self._agent.run()
                finally:
                    lock.release()

            except Exception as exc:  # noqa: BLE001 — tout doit finir au journal
                # Sans cette capture, une erreur ici disparaîtrait : un service
                # n'a ni console ni sortie standard visible.
                servicemanager.LogErrorMsg(f"{SERVICE_NAME} : arrêt sur erreur — {exc}")
            finally:
                # Prévenir le fil principal, sinon le service resterait
                # « en cours d'exécution » avec une boucle morte.
                win32event.SetEvent(self._wake)


def _ensure_import_path() -> None:
    """Rend les modules de l'agent importables depuis le contexte du service.

    Un service démarre avec un répertoire courant imposé par Windows
    (`C:\\Windows\\System32`), pas celui de l'installation : les imports
    relatifs au dossier courant échoueraient.
    """
    here = str(Path(__file__).resolve().parent)
    if here not in sys.path:
        sys.path.insert(0, here)
    parent = str(Path(__file__).resolve().parent.parent.parent)
    if parent not in sys.path:
        sys.path.insert(0, parent)


def main(argv=None) -> int:
    """Point d'entrée `install` / `remove` / `start` / `stop` / `debug`."""
    if not PYWIN32_AVAILABLE:
        print(
            "pywin32 est requis pour le mode service Windows.\n"
            "  pip install pywin32",
            file=sys.stderr,
        )
        return 1

    argv = list(sys.argv if argv is None else argv)
    if len(argv) == 1:
        # Lancé sans argument par le gestionnaire de services : c'est Windows
        # qui nous démarre, pas un humain.
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(CBCAgentService)
        servicemanager.StartServiceCtrlDispatcher()
        return 0

    win32serviceutil.HandleCommandLine(CBCAgentService, argv=argv)
    return 0


if __name__ == "__main__":
    _ensure_import_path()
    sys.exit(main())
