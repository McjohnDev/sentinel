# -*- mode: python ; coding: utf-8 -*-
# Frozen from agent/packaging; run: pyinstaller --noconfirm packaging/agent.spec
# (cwd = agent/) or from repo: pyinstaller --noconfirm agent/packaging/agent.spec

import os
import sys
from PyInstaller.utils.hooks import collect_submodules

spec_dir = os.path.dirname(os.path.abspath(SPEC))
agent_dir = os.path.abspath(os.path.join(spec_dir, ".."))
src_dir = os.path.join(agent_dir, "src")
repo_root = os.path.abspath(os.path.join(agent_dir, ".."))
config_yaml = os.path.join(agent_dir, "config.yaml")

for p in (src_dir, repo_root):
    if p not in sys.path:
        sys.path.insert(0, p)

hiddenimports = [
    "psutil",
    "requests",
    "yaml",
    "pyyaml",
    "pydantic",
    "urllib3",
    "instance_lock",
    "durable_buffer",
    "task_handler",
    "log_collector",
    "disk_metrics",
    "remote_config",
    "session_state",
    "action_plugins",
    "updater",
    # Ajoutés avec la CLI et le mode service (AGT-001b / point 4).
    "cli",
    "agent_paths",
    "runtime_info",
    "windows_service",
    # pywin32 : PyInstaller ne détecte pas ces imports, faits par le
    # gestionnaire de services et non par notre code. `win32timezone` est
    # chargé paresseusement par pywin32 et manque systématiquement sans
    # déclaration explicite.
    "win32serviceutil",
    "win32service",
    "win32event",
    "servicemanager",
    "win32timezone",
]
hiddenimports += collect_submodules("plugins")
hiddenimports += collect_submodules("shared.protocols")

a = Analysis(
    [os.path.join(src_dir, "agent.py")],
    pathex=[src_dir, repo_root],
    binaries=[],
    datas=[(config_yaml, ".")],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

# Windows Defender often locks a freshly written exe and breaks PyInstaller's
# PE timestamp stamp. Skipping it does not affect runtime.
try:
    from PyInstaller.utils.win32 import winutils as _winutils

    def _skip_win_pe_touch(*_args, **_kwargs):
        return None

    _winutils.set_exe_build_timestamp = _skip_win_pe_touch
    _winutils.update_exe_pe_checksum = _skip_win_pe_touch
except Exception:
    pass

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="cbc-agent",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="cbc-agent",
)
