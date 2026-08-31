"""Disk partition collection — primary path + selective alert mounts."""

from __future__ import annotations

import platform
from typing import Any, Dict, List, Optional, Tuple

import psutil

_SKIP_FSTYPES = {"", "cdrom", "iso9660"}


def default_disk_path() -> str:
    if platform.system().lower() == "windows":
        return "C:\\"
    return "/"


def normalize_mount(mount: str) -> str:
    m = (mount or "").strip()
    if len(m) >= 2 and m[1] == ":":
        return m.rstrip("\\").upper() + "\\"
    return m.rstrip("/") or "/"


def _windows_letter(mount: str) -> Optional[str]:
    m = (mount or "").strip()
    if len(m) >= 2 and m[1] == ":":
        return m[0].upper()
    return None


def _windows_volume_label(mount: str) -> Optional[str]:
    """Best-effort Windows volume label (e.g. 'OS', 'Data')."""
    if platform.system().lower() != "windows":
        return None
    try:
        import ctypes

        root = normalize_mount(mount)
        volume_name = ctypes.create_unicode_buffer(261)
        fs_name = ctypes.create_unicode_buffer(261)
        ok = ctypes.windll.kernel32.GetVolumeInformationW(  # type: ignore[attr-defined]
            ctypes.c_wchar_p(root),
            volume_name,
            ctypes.sizeof(volume_name),
            None,
            None,
            None,
            fs_name,
            ctypes.sizeof(fs_name),
        )
        if ok and volume_name.value:
            return str(volume_name.value)
    except Exception:
        return None
    return None


def _partition_name(mount: str, fstype: str, label: Optional[str] = None) -> str:
    letter = _windows_letter(mount)
    if letter:
        return f"{letter}: ({label})" if label else f"{letter}:"
    if label:
        return f"{label} ({mount})"
    return mount or fstype or "disk"


def collect_disk_partitions(disk_cfg: Optional[Dict[str, Any]] = None) -> Tuple[Dict[str, float], List[Dict[str, Any]]]:
    """Return primary disk summary + all partition rows for heartbeat."""
    cfg = disk_cfg or {}
    primary_path = normalize_mount(str(cfg.get("path") or default_disk_path()))
    alert_mounts_raw = cfg.get("alert_mounts")
    alert_mounts: Optional[List[str]] = None
    if isinstance(alert_mounts_raw, list) and alert_mounts_raw:
        alert_mounts = [normalize_mount(str(m)) for m in alert_mounts_raw if m]

    disks: List[Dict[str, Any]] = []
    for part in psutil.disk_partitions(all=False):
        if not part.mountpoint or part.fstype in _SKIP_FSTYPES:
            continue
        mount = normalize_mount(part.mountpoint)
        try:
            usage = psutil.disk_usage(part.mountpoint)
        except (PermissionError, OSError):
            continue
        label = _windows_volume_label(part.mountpoint)
        letter = _windows_letter(part.mountpoint)
        disks.append(
            {
                "name": _partition_name(part.mountpoint, part.fstype or "", label),
                "mount": mount,
                "letter": letter,
                "label": label,
                "device": getattr(part, "device", None) or None,
                "fstype": part.fstype or "unknown",
                "percent": round(float(usage.percent), 2),
                "total_gb": round(usage.total / (1024**3), 2),
                "used_gb": round(usage.used / (1024**3), 2),
                "free_gb": round(usage.free / (1024**3), 2),
            }
        )

    if alert_mounts:
        alert_set = set(alert_mounts)
        for row in disks:
            row["alert"] = row["mount"] in alert_set
    else:
        for row in disks:
            row["alert"] = row["mount"] == primary_path

    primary = next((d for d in disks if d["mount"] == primary_path), disks[0] if disks else None)
    if primary:
        summary = {
            "disk_percent": primary["percent"],
            "disk_total_gb": primary["total_gb"],
            "disk_used_gb": primary["used_gb"],
            "disk_free_gb": primary["free_gb"],
            "disk_mount": primary["mount"],
        }
    else:
        try:
            usage = psutil.disk_usage(cfg.get("path") or default_disk_path())
            summary = {
                "disk_percent": float(usage.percent),
                "disk_total_gb": round(usage.total / (1024**3), 2),
                "disk_used_gb": round(usage.used / (1024**3), 2),
                "disk_free_gb": round(usage.free / (1024**3), 2),
                "disk_mount": primary_path,
            }
        except OSError:
            summary = {
                "disk_percent": 0.0,
                "disk_total_gb": 0.0,
                "disk_used_gb": 0.0,
                "disk_free_gb": 0.0,
                "disk_mount": primary_path,
            }

    return summary, disks
