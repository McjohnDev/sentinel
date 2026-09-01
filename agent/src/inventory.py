"""Inventaire de l'hôte : services disponibles, applications, pilotes.

Trois usages, un seul relevé.

* **Services disponibles.** L'exploitant ne doit pas *taper* un nom de
  service : une faute de frappe produit une surveillance qui ne surveille
  rien, et personne ne s'en aperçoit — le service reste « inconnu » au lieu
  d'être « arrêté ». La plateforme choisit donc parmi ce que l'hôte déclare
  réellement offrir.
* **Applications installées.** Savoir ce qui tourne sur le parc, et depuis
  quelle version.
* **Pilotes.** Sur un parc bancaire, un pilote de périphérique de paiement ou
  de carte à puce qui recule d'une version explique des incidents qu'aucune
  métrique système ne montre.

Ce relevé est **coûteux** — il interroge la base de registre ou le
gestionnaire de paquets — et ne bouge que rarement. Il ne voyage donc pas
avec le battement : il part sur sa propre route, à cadence lente.

Rien ici ne fait échouer l'agent. Un inventaire indisponible se rend vide,
avec la raison ; il vaut mieux un hôte supervisé sans inventaire qu'un hôte
qui ne bat plus parce qu'un pilote refuse de se laisser lire.
"""

from __future__ import annotations

import csv
import io
import logging
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

try:
    import psutil
except ImportError:  # pragma: no cover - dépendance déclarée
    psutil = None

logger = logging.getLogger("cbc-agent.inventory")

#: Les commandes d'inventaire sont lentes ; au-delà, on renonce plutôt que de
#: retarder le prochain battement.
COMMAND_TIMEOUT = 60

#: Garde-fou de volume. Un poste de développement peut déclarer des milliers
#: de paquets ; les envoyer tous gonflerait la charge utile sans rien
#: apporter. La troncature est **signalée**, jamais silencieuse.
MAX_ROWS = 1000


@dataclass
class Inventory:
    services: List[Dict[str, Any]] = field(default_factory=list)
    applications: List[Dict[str, Any]] = field(default_factory=list)
    drivers: List[Dict[str, Any]] = field(default_factory=list)
    truncated: List[str] = field(default_factory=list)
    unavailable: List[str] = field(default_factory=list)

    def as_payload(self) -> Dict[str, Any]:
        return {
            "services": self.services,
            "applications": self.applications,
            "drivers": self.drivers,
            "truncated": self.truncated,
            "unavailable": self.unavailable,
        }


#: Sous Windows, les outils console écrivent dans la page de codes OEM, pas en
#: UTF-8 ni en cp1252. Décodée au petit bonheur, une en-tête accentuée comme
#: « État » arrive en « ‰tat » et aucune correspondance ne tombe juste. Le
#: codec « oem » de Python règle la question à la source.
_CONSOLE_ENCODING = "oem" if sys.platform == "win32" else None


def _run(command: List[str]) -> Optional[str]:
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=COMMAND_TIMEOUT,
            check=False, errors="replace", encoding=_CONSOLE_ENCODING,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        logger.debug("Commande %s indisponible : %s", command[0], exc)
        return None
    if result.returncode != 0 and not result.stdout:
        return None
    return result.stdout


def _cap(rows: List[Dict[str, Any]], label: str, report: Inventory) -> List[Dict[str, Any]]:
    if len(rows) > MAX_ROWS:
        report.truncated.append("%s (%d retenus sur %d)" % (label, MAX_ROWS, len(rows)))
        return rows[:MAX_ROWS]
    return rows


# ------------------------------------------------------ services disponibles


def available_services() -> List[Dict[str, Any]]:
    """Services que l'hôte déclare offrir, avec leur état courant."""
    if sys.platform == "win32":
        return _windows_services()
    if sys.platform == "darwin":
        return _launchd_services()
    return _systemd_services()


def _windows_services() -> List[Dict[str, Any]]:
    if psutil is None or not hasattr(psutil, "win_service_iter"):
        return []
    rows = []
    try:
        for service in psutil.win_service_iter():
            try:
                info = service.as_dict()
            except Exception:
                continue
            rows.append(
                {
                    "name": info.get("name"),
                    "display_name": info.get("display_name"),
                    "status": (info.get("status") or "unknown"),
                    "start_type": info.get("start_type"),
                }
            )
    except Exception as exc:
        logger.warning("Énumération des services impossible : %s", exc)
    return [r for r in rows if r.get("name")]


def _systemd_services() -> List[Dict[str, Any]]:
    output = _run(
        ["systemctl", "list-units", "--type=service", "--all", "--no-legend", "--no-pager", "--plain"]
    )
    if output is None:
        return []
    rows = []
    for line in output.splitlines():
        parts = line.split(None, 4)
        if len(parts) < 4 or not parts[0].endswith(".service"):
            continue
        name = parts[0][: -len(".service")]
        active = parts[2]
        rows.append(
            {
                "name": name,
                "display_name": parts[4].strip() if len(parts) > 4 else name,
                "status": "running" if active == "active" else "stopped",
                "start_type": None,
            }
        )
    return rows


def _launchd_services() -> List[Dict[str, Any]]:
    output = _run(["launchctl", "list"])
    if output is None:
        return []
    rows = []
    for line in output.splitlines()[1:]:
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        label = parts[2].strip()
        if not label:
            continue
        rows.append(
            {
                "name": label,
                "display_name": label,
                "status": "stopped" if parts[0].strip() == "-" else "running",
                "start_type": None,
            }
        )
    return rows


# -------------------------------------------------------------- applications


def applications() -> List[Dict[str, Any]]:
    if sys.platform == "win32":
        return _windows_applications()
    if sys.platform == "darwin":
        return _macos_applications()
    return _linux_applications()


def _windows_applications() -> List[Dict[str, Any]]:
    """Lit la base de registre — la seule source complète sous Windows.

    Les deux ruches et les deux vues (32 et 64 bits) sont parcourues : une
    application 32 bits sur un système 64 bits n'apparaît que dans la vue
    `WOW6432Node`, et l'omettre donnerait un inventaire silencieusement
    incomplet.
    """
    try:
        import winreg
    except ImportError:  # pragma: no cover - hors Windows
        return []

    roots = [
        (winreg.HKEY_LOCAL_MACHINE, winreg.KEY_WOW64_64KEY),
        (winreg.HKEY_LOCAL_MACHINE, winreg.KEY_WOW64_32KEY),
        (winreg.HKEY_CURRENT_USER, 0),
    ]
    path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
    seen = set()
    rows: List[Dict[str, Any]] = []

    for hive, view in roots:
        try:
            key = winreg.OpenKey(hive, path, 0, winreg.KEY_READ | view)
        except OSError:
            continue
        try:
            count = winreg.QueryInfoKey(key)[0]
            for index in range(count):
                try:
                    sub_name = winreg.EnumKey(key, index)
                    with winreg.OpenKey(key, sub_name, 0, winreg.KEY_READ | view) as sub:
                        name = _reg_value(winreg, sub, "DisplayName")
                        if not name:
                            continue
                        # Les correctifs Windows ne sont pas des applications :
                        # les mêler noierait l'inventaire utile.
                        if _reg_value(winreg, sub, "SystemComponent") == 1:
                            continue
                        version = _reg_value(winreg, sub, "DisplayVersion")
                        identity = (str(name), str(version or ""))
                        if identity in seen:
                            continue
                        seen.add(identity)
                        rows.append(
                            {
                                "name": str(name),
                                "version": str(version) if version else None,
                                "publisher": _as_text(_reg_value(winreg, sub, "Publisher")),
                                "install_date": _as_text(_reg_value(winreg, sub, "InstallDate")),
                            }
                        )
                except OSError:
                    continue
        finally:
            key.Close()
    return sorted(rows, key=lambda r: r["name"].lower())


def _reg_value(winreg, key, name):
    try:
        return winreg.QueryValueEx(key, name)[0]
    except OSError:
        return None


def _as_text(value: Any) -> Optional[str]:
    return str(value) if value not in (None, "") else None


def _linux_applications() -> List[Dict[str, Any]]:
    output = _run(["dpkg-query", "-W", "-f=${Package}\\t${Version}\\t${Maintainer}\\n"])
    if output is not None:
        rows = []
        for line in output.splitlines():
            parts = line.split("\t")
            if not parts or not parts[0].strip():
                continue
            rows.append(
                {
                    "name": parts[0].strip(),
                    "version": parts[1].strip() if len(parts) > 1 and parts[1].strip() else None,
                    "publisher": parts[2].strip() if len(parts) > 2 and parts[2].strip() else None,
                    "install_date": None,
                }
            )
        return rows

    output = _run(["rpm", "-qa", "--queryformat", "%{NAME}\\t%{VERSION}-%{RELEASE}\\t%{VENDOR}\\n"])
    if output is None:
        return []
    rows = []
    for line in output.splitlines():
        parts = line.split("\t")
        if not parts or not parts[0].strip():
            continue
        rows.append(
            {
                "name": parts[0].strip(),
                "version": parts[1].strip() if len(parts) > 1 else None,
                "publisher": parts[2].strip() if len(parts) > 2 else None,
                "install_date": None,
            }
        )
    return rows


def _macos_applications() -> List[Dict[str, Any]]:
    import os

    rows = []
    for folder in ("/Applications", os.path.expanduser("~/Applications")):
        try:
            entries = os.listdir(folder)
        except OSError:
            continue
        for entry in entries:
            if entry.endswith(".app"):
                rows.append(
                    {"name": entry[: -len(".app")], "version": None, "publisher": None, "install_date": None}
                )
    return rows


# ------------------------------------------------------------------ pilotes


def drivers() -> List[Dict[str, Any]]:
    if sys.platform == "win32":
        return _windows_drivers()
    if sys.platform == "darwin":
        return _macos_drivers()
    return _linux_drivers()


_HEADER_ACCENTS = str.maketrans("àâäéèêëîïôöùûüç", "aaaeeeeiioouuuc")


def _fold_header(name: Any) -> str:
    """Réduit une en-tête à une forme comparable, quelle que soit la langue."""
    folded = str(name or "").strip().lower().translate(_HEADER_ACCENTS)
    return "".join(c for c in folded if c.isalnum())


def _pick(record: Dict[str, Any], *wanted: str) -> Optional[str]:
    """Valeur de la première colonne dont l'en-tête correspond.

    La correspondance se fait sur la forme repliée : l'outil console est
    traduit, et coder les intitulés anglais en dur donnait un inventaire
    silencieusement amputé sur un Windows français.
    """
    for key, value in record.items():
        if _fold_header(key) in wanted:
            text = str(value or "").strip()
            return text or None
    return None


def _windows_drivers() -> List[Dict[str, Any]]:
    output = _run(["driverquery", "/FO", "CSV", "/V"])
    if output is None:
        output = _run(["driverquery", "/FO", "CSV"])
    if output is None:
        return []
    rows = []
    try:
        reader = csv.DictReader(io.StringIO(output))
        for record in reader:
            name = _pick(record, "modulename", "nomdumodule")
            if not name:
                continue
            rows.append(
                {
                    "name": name,
                    "display_name": _pick(record, "displayname", "nomcomplet"),
                    "version": _pick(record, "driverversion", "versiondupilote"),
                    # « etat » (État) porte Running/Stopped ; « statut »
                    # (Status) porte OK/Erreur — ce n'est pas la même chose.
                    "state": _pick(record, "state", "etat"),
                }
            )
    except csv.Error as exc:
        logger.warning("Sortie driverquery illisible : %s", exc)
        return []
    return rows


def _linux_drivers() -> List[Dict[str, Any]]:
    """Modules chargés par le noyau — l'équivalent Linux d'un pilote."""
    output = _run(["lsmod"])
    if output is None:
        return []
    rows = []
    for line in output.splitlines()[1:]:
        parts = line.split()
        if not parts:
            continue
        rows.append(
            {"name": parts[0], "display_name": None, "version": None, "state": "loaded"}
        )
    return rows


def _macos_drivers() -> List[Dict[str, Any]]:
    output = _run(["kmutil", "showloaded"]) or _run(["kextstat"])
    if output is None:
        return []
    rows = []
    for line in output.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 6:
            continue
        rows.append({"name": parts[5], "display_name": None, "version": None, "state": "loaded"})
    return rows


# ------------------------------------------------------------------ relevé


def collect() -> Inventory:
    """Relève l'inventaire complet, sans jamais lever.

    Chaque section est isolée : un gestionnaire de paquets absent ou un
    `driverquery` qui refuse de répondre ne doit pas emporter les deux autres.
    Ce qui manque est **nommé** dans `unavailable`, pour qu'un inventaire
    partiel ne se lise pas comme un hôte sans applications.
    """
    report = Inventory()

    for label, gather, sink in (
        ("services", available_services, "services"),
        ("applications", applications, "applications"),
        ("drivers", drivers, "drivers"),
    ):
        try:
            rows = gather() or []
        except Exception as exc:  # noqa: BLE001
            logger.warning("Inventaire %s indisponible : %s", label, exc)
            report.unavailable.append(label)
            continue
        if not rows:
            report.unavailable.append(label)
        setattr(report, sink, _cap(rows, label, report))

    return report


# ---------------------------------------------------------------- transmission


class InventoryPushFailed(RuntimeError):
    """L'inventaire n'a pas pu être transmis."""


def push(config, credentials, report: "Inventory", *, session=None) -> Dict[str, Any]:
    """Envoie l'inventaire à la plateforme."""
    import requests

    http = session or requests.Session()
    try:
        response = http.post(
            config.api_url("agents/inventory"),
            json=report.as_payload(),
            headers={"Authorization": credentials.auth_key},
            timeout=max(config.timeout_seconds, 30),
            verify=config.tls_verify,
        )
    except Exception as exc:  # noqa: BLE001 - requests expose plusieurs familles
        raise InventoryPushFailed("Inventaire non transmis : %s" % exc)

    if response.status_code >= 400:
        raise InventoryPushFailed("Inventaire refusé (%s)." % response.status_code)
    try:
        return response.json()
    except ValueError:
        return {}
