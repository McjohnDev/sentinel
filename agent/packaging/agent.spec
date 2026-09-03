# -*- mode: python ; coding: utf-8 -*-
"""Gel de l'agent CBC en un exécutable autonome.

    pyinstaller --noconfirm agent/packaging/agent.spec

**Réécrit après la refonte de l'agent.** Le fichier précédent déclarait un
point d'entrée (`agent.py`) et une dizaine de modules — `durable_buffer`,
`task_handler`, `log_collector`, `action_plugins`, `updater`, `windows_service`
— qui n'existent plus, ainsi que les paquets `plugins` et `shared.protocols`
retirés depuis. Il ne construisait donc plus rien, et l'aurait signalé tard :
PyInstaller échoue sur l'import, pas sur la déclaration.

Ce qui est déclaré ici l'est parce que PyInstaller ne peut pas le deviner :
`psutil` charge des extensions selon la plateforme, et l'agent importe ses
propres modules par leur nom court (le dossier `src` étant sur le chemin),
non par un paquet que l'analyse statique suivrait.
"""

import os
import sys

spec_dir = os.path.dirname(os.path.abspath(SPEC))
agent_dir = os.path.abspath(os.path.join(spec_dir, ".."))
src_dir = os.path.join(agent_dir, "src")
config_yaml = os.path.join(agent_dir, "config.yaml")

if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

#: Les modules de l'agent, importés par nom court depuis `src`. Les lister
#: évite qu'un module atteint seulement par un chemin conditionnel — comme
#: `inventory`, sollicité un battement sur deux cent quarante — manque à
#: l'exécution, des heures après une installation apparemment réussie.
hiddenimports = [
    "agent_paths",
    "cli",
    "collectors",
    "config",
    "enrollment",
    "facts",
    "heartbeat",
    "identity",
    "instance_lock",
    "inventory",
    "metrics",
    "plan",
    "runner",
    "session",
    # Dépendances tierces dont les imports sont dynamiques.
    "psutil",
    "requests",
    "urllib3",
    "yaml",
]

a = Analysis(
    [os.path.join(src_dir, "cli.py")],
    pathex=[src_dir],
    binaries=[],
    # Le fichier de configuration livré ne porte aucun jeton : il serait
    # diffusé avec chaque installation. Le jeton arrive à l'enrôlement.
    datas=[(config_yaml, ".")],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy", "pytest"],
    noarchive=False,
)

pyz = PYZ(a.pure)

# Windows Defender garde parfois la main sur un exécutable fraîchement écrit,
# ce qui fait échouer l'horodatage PE. L'ignorer n'a aucun effet à l'exécution.
try:
    from PyInstaller.utils.win32 import winutils as _winutils

    def _ne_rien_faire(*_args, **_kwargs):
        return None

    _winutils.set_exe_build_timestamp = _ne_rien_faire
    _winutils.update_exe_pe_checksum = _ne_rien_faire
except Exception:  # noqa: BLE001 — absent hors Windows, sans conséquence
    pass

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="cbc-agent",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    # Console conservée : l'agent s'exécute en service, mais `status`,
    # `enroll` et `configure` sont lancés à la main par un exploitant qui doit
    # en lire la sortie. Un binaire sans console rendrait ces verbes muets.
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
