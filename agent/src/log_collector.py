"""Log collectors (AGT-030–038): files, journald, Windows Event Log."""

from __future__ import annotations

import json
import os
import platform
import re
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from glob import glob
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


SEVERITY_ORDER = {"debug": 0, "info": 1, "notice": 2, "warning": 3, "error": 4, "critical": 5}

SYSLOG_RE = re.compile(
    r"^(?P<ts>\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+(?P<host>\S+)\s+(?P<proc>\S+):\s+(?P<msg>.*)$"
)

SYSLOG_PRIORITY = {
    0: "critical",
    1: "critical",
    2: "critical",
    3: "error",
    4: "warning",
    5: "notice",
    6: "info",
    7: "debug",
}

WIN_LEVEL = {
    1: "critical",
    2: "error",
    3: "warning",
    4: "info",
    5: "debug",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def parse_line(line: str, parser: str = "raw") -> Dict[str, Any]:
    raw = line.rstrip("\n")
    event: Dict[str, Any] = {
        "ts": _now().isoformat(),
        "severity": "info",
        "message": raw,
        "parsed": False,
        "raw": raw,
        "source": "file",
    }
    if parser == "json":
        try:
            data = json.loads(raw)
            event["parsed"] = True
            event["message"] = str(data.get("message") or data.get("msg") or raw)
            event["severity"] = str(data.get("level") or data.get("severity") or "info").lower()
            ts = data.get("ts") or data.get("timestamp") or data.get("time")
            if ts:
                event["ts"] = str(ts)
        except json.JSONDecodeError:
            pass
    elif parser == "syslog":
        m = SYSLOG_RE.match(raw)
        if m:
            event["parsed"] = True
            event["message"] = m.group("msg")
            event["severity"] = "info"
    return event


def _passes_filters(
    event: Dict[str, Any],
    severity_floor: str,
    include_re: Optional[re.Pattern[str]],
    exclude_re: Optional[re.Pattern[str]],
) -> bool:
    sev = str(event.get("severity") or "info").lower()
    floor = SEVERITY_ORDER.get(severity_floor, 0)
    if SEVERITY_ORDER.get(sev, 1) < floor:
        return False
    msg = event.get("message") or ""
    if include_re and not include_re.search(msg):
        return False
    if exclude_re and exclude_re.search(msg):
        return False
    return True


@dataclass
class RateLimiter:
    max_bytes_per_min: int = 5 * 1024 * 1024
    window: List[tuple] = field(default_factory=list)  # (ts, nbytes)

    def allow(self, nbytes: int) -> bool:
        now = time.time()
        self.window = [(t, n) for t, n in self.window if now - t < 60]
        used = sum(n for _, n in self.window)
        if used + nbytes > self.max_bytes_per_min:
            return False
        self.window.append((now, nbytes))
        return True

    def used_bytes(self) -> int:
        now = time.time()
        self.window = [(t, n) for t, n in self.window if now - t < 60]
        return sum(n for _, n in self.window)


class _FilterMixin:
    severity_floor: str
    include_re: Optional[re.Pattern[str]]
    exclude_re: Optional[re.Pattern[str]]
    limiter: RateLimiter
    spill_path: Path
    alert_patterns: List[re.Pattern[str]]
    dropped: int
    rate_limited: bool

    #: Plafond du fichier de débordement. Sans borne, le mécanisme censé
    #: éviter la perte remplissait le disque de l'hôte supervisé.
    spill_max_bytes: int = 32 * 1024 * 1024

    def _spill(self, raw: str) -> None:
        """Écrit une ligne écartée dans le fichier de débordement, borné.

        Le fichier était auparavant en écriture seule, jamais relu ni plafonné :
        il croissait sans limite et son contenu était perdu de fait. Il est
        désormais borné par rotation (un seul fichier de secours conservé) et
        relu par `_drain_spill` dès que le débit le permet.
        """
        try:
            limit = getattr(self, "spill_max_bytes", 32 * 1024 * 1024)
            if limit > 0 and self.spill_path.exists():
                if self.spill_path.stat().st_size >= limit:
                    # Conserver une génération : au-delà, la donnée la plus
                    # ancienne est explicitement abandonnée.
                    backup = self.spill_path.with_suffix(self.spill_path.suffix + ".1")
                    backup.unlink(missing_ok=True)
                    self.spill_path.replace(backup)
            with self.spill_path.open("a", encoding="utf-8") as spill:
                spill.write(raw)
        except OSError:
            # Un débordement impossible à écrire ne doit pas interrompre la
            # collecte : la ligne est perdue et comptée dans `dropped`.
            pass

    def _drain_spill(self, max_lines: int = 2000) -> List[str]:
        """Reprend les lignes mises de côté, dans la limite du débit courant.

        C'est ce qui distingue un débordement d'une perte : sans relecture, le
        fichier n'était qu'un cimetière.
        """
        if not self.spill_path.exists():
            return []
        try:
            content = self.spill_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return []

        lines = [ln for ln in content.splitlines(keepends=True) if ln.strip()]
        if not lines:
            self.spill_path.unlink(missing_ok=True)
            return []

        recovered: List[str] = []
        for idx, line in enumerate(lines):
            if len(recovered) >= max_lines:
                lines = lines[idx:]
                break
            nbytes = len(line.encode("utf-8"))
            if not self.limiter.allow(nbytes):
                # Budget épuisé : le reste attend le prochain cycle.
                lines = lines[idx:]
                break
            recovered.append(line)
        else:
            lines = []

        try:
            if lines:
                self.spill_path.write_text("".join(lines), encoding="utf-8")
            else:
                self.spill_path.unlink(missing_ok=True)
        except OSError:
            pass
        return recovered

    def _admit(self, event: Dict[str, Any], spill_text: str) -> Optional[Dict[str, Any]]:
        raw = spill_text if spill_text.endswith("\n") else spill_text + "\n"
        nbytes = len(raw.encode("utf-8"))
        if not self.limiter.allow(nbytes):
            self.rate_limited = True
            self.dropped += 1
            self._spill(raw)
            return None
        if not _passes_filters(event, self.severity_floor, self.include_re, self.exclude_re):
            self.dropped += 1
            return None
        return event

    def _pattern_alerts(self, event: Dict[str, Any]) -> List[Dict[str, Any]]:
        msg = event.get("message") or ""
        for pat in self.alert_patterns:
            if pat.search(msg):
                return [event]
        return []


def _compile_optional(pattern: Optional[str]) -> Optional[re.Pattern[str]]:
    return re.compile(pattern) if pattern else None


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _save_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


class FileLogCollector(_FilterMixin):
    def __init__(
        self,
        patterns: List[str],
        offset_path: str | Path,
        parser: str = "raw",
        severity_floor: str = "debug",
        include_regex: Optional[str] = None,
        exclude_regex: Optional[str] = None,
        multiline_start: Optional[str] = None,
        max_bytes_per_min: int = 5 * 1024 * 1024,
        spill_path: Optional[str | Path] = None,
        alert_patterns: Optional[List[str]] = None,
        limiter: Optional[RateLimiter] = None,
    ) -> None:
        self.patterns = patterns
        self.offset_path = Path(offset_path)
        self.offset_path.parent.mkdir(parents=True, exist_ok=True)
        self.parser = parser
        self.severity_floor = severity_floor.lower()
        self.include_re = _compile_optional(include_regex)
        self.exclude_re = _compile_optional(exclude_regex)
        self.multiline_start = re.compile(multiline_start) if multiline_start else None
        self.limiter = limiter or RateLimiter(max_bytes_per_min)
        self.spill_path = Path(spill_path) if spill_path else self.offset_path.parent / "spill.log"
        self.alert_patterns = [re.compile(p) for p in (alert_patterns or [])]
        self.dropped = 0
        self.rate_limited = False
        self._multiline_buf: List[str] = []
        self._multiline_channel = ""
        self.offsets: Dict[str, Dict[str, Any]] = self._load_offsets()

    def _load_offsets(self) -> Dict[str, Dict[str, Any]]:
        data = _load_json(self.offset_path)
        return {k: v for k, v in data.items() if isinstance(v, dict) and "offset" in v}

    def _save_offsets(self) -> None:
        existing = _load_json(self.offset_path)
        existing.update(self.offsets)
        _save_json(self.offset_path, existing)

    def _files(self) -> List[Path]:
        found: List[Path] = []
        for pattern in self.patterns:
            for match in glob(pattern, recursive=True):
                p = Path(match)
                if p.is_file():
                    found.append(p)
        return found

    def _passes_filters(self, event: Dict[str, Any]) -> bool:
        return _passes_filters(event, self.severity_floor, self.include_re, self.exclude_re)

    def _read_new_lines(self, path: Path) -> List[str]:
        """Lit les lignes ajoutées depuis le dernier passage.

        La position était mémorisée sous la seule clé du chemin, et la
        rotation n'était détectée que par un rétrécissement du fichier
        (`size < offset`). Avec une rotation par renommage — le cas de
        logrotate : `app.log` devient `app.log.1`, un nouveau `app.log` est
        créé — le chemin ne change pas. Si le nouveau fichier avait déjà
        dépassé l'ancienne position au passage suivant, la lecture reprenait
        à cette position et **sautait le début du nouveau fichier**, la
        première ligne lue étant un fragment de ligne.

        L'identité du fichier (device + inode) est donc mémorisée avec la
        position : tout changement d'identité repart de zéro.
        """
        key = str(path)
        stat = path.stat()
        size = stat.st_size
        # st_ino est renseigné sur Windows par Python 3.5+ (index de fichier
        # NTFS) comme sur POSIX ; 0 signale une identité indisponible.
        identity = f"{stat.st_dev}:{stat.st_ino}"

        state = self.offsets.get(key, {"offset": 0, "size": 0})
        offset = int(state.get("offset") or 0)
        previous_identity = state.get("identity")

        if previous_identity is not None and previous_identity != identity:
            # Fichier remplacé : la position de l'ancien n'a aucun sens ici.
            offset = 0
        elif size < offset:
            offset = 0  # troncature sur place

        lines: List[str] = []
        with path.open("r", encoding="utf-8", errors="replace") as f:
            f.seek(offset)
            for line in f:
                lines.append(line)
            self.offsets[key] = {
                "offset": f.tell(),
                "size": size,
                "identity": identity,
            }
        return lines

    def _flush_multiline(self) -> Optional[Tuple[str, str]]:
        if not self._multiline_buf:
            return None
        joined = "".join(self._multiline_buf)
        channel = self._multiline_channel
        self._multiline_buf = []
        return channel, joined

    def collect(self) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Return (log events, immediate alert events for pattern matches)."""
        events: List[Dict[str, Any]] = []
        alerts: List[Dict[str, Any]] = []
        self.rate_limited = False

        raw_lines: List[Tuple[str, str]] = []
        # Reprendre d'abord ce qui avait débordé : ces lignes sont plus
        # anciennes que celles à lire maintenant.
        for recovered in self._drain_spill():
            raw_lines.append(("spill", recovered))
        for path in self._files():
            try:
                new_lines = self._read_new_lines(path)
            except OSError:
                continue
            channel = path.name
            for line in new_lines:
                if self.multiline_start:
                    if self.multiline_start.search(line) and self._multiline_buf:
                        flushed = self._flush_multiline()
                        if flushed:
                            raw_lines.append(flushed)
                    self._multiline_buf.append(line)
                    self._multiline_channel = channel
                else:
                    raw_lines.append((channel, line))
        flushed = self._flush_multiline()
        if flushed:
            raw_lines.append(flushed)

        for channel, line in raw_lines:
            event = parse_line(line, self.parser)
            event["source"] = "file"
            event["channel"] = channel
            admitted = self._admit(event, line)
            if admitted is None:
                continue
            events.append(admitted)
            alerts.extend(self._pattern_alerts(admitted))

        self._save_offsets()
        return events, alerts


JournaldReader = Callable[[Optional[str], List[str], int], Tuple[List[Dict[str, Any]], Optional[str]]]
WinEvtReader = Callable[[str, int, int], List[Dict[str, Any]]]
WinEvtBookmark = Callable[[str], int]


def journalctl_read(
    cursor: Optional[str], units: List[str], max_entries: int
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Read journald via journalctl (no systemd-python required)."""
    cmd = ["journalctl", "-o", "json", "--no-pager", "-n", str(max_entries)]
    if cursor:
        cmd = ["journalctl", "-o", "json", "--no-pager", "--after-cursor", cursor, "-n", str(max_entries)]
    for unit in units:
        cmd.extend(["-u", unit])
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return [], cursor
    records: List[Dict[str, Any]] = []
    last_cursor = cursor
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict):
            records.append(rec)
            last_cursor = rec.get("__CURSOR") or last_cursor
    return records, last_cursor


def journald_record_to_event(rec: Dict[str, Any]) -> Dict[str, Any]:
    try:
        prio = int(rec.get("PRIORITY", 6))
    except (TypeError, ValueError):
        prio = 6
    usec = rec.get("__REALTIME_TIMESTAMP")
    ts = _now().isoformat()
    try:
        if usec is not None:
            ts = datetime.fromtimestamp(int(usec) / 1_000_000, tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        pass
    unit = str(rec.get("_SYSTEMD_UNIT") or rec.get("SYSLOG_IDENTIFIER") or "journal")
    message = rec.get("MESSAGE")
    if isinstance(message, list):
        message = " ".join(str(x) for x in message)
    message = str(message or "")
    return {
        "ts": ts,
        "severity": SYSLOG_PRIORITY.get(prio, "info"),
        "message": message,
        "parsed": True,
        "raw": message,
        "source": "journald",
        "channel": unit,
    }


class JournaldCollector(_FilterMixin):
    """Linux journald source (AGT-031). Cursor persisted; first run seeds without backfill."""

    def __init__(
        self,
        state_path: str | Path,
        units: Optional[List[str]] = None,
        max_entries: int = 200,
        severity_floor: str = "debug",
        include_regex: Optional[str] = None,
        exclude_regex: Optional[str] = None,
        max_bytes_per_min: int = 5 * 1024 * 1024,
        spill_path: Optional[str | Path] = None,
        alert_patterns: Optional[List[str]] = None,
        limiter: Optional[RateLimiter] = None,
        reader: Optional[JournaldReader] = None,
    ) -> None:
        self.state_path = Path(state_path)
        self.units = [u for u in (units or []) if u]
        self.max_entries = max_entries
        self.severity_floor = severity_floor.lower()
        self.include_re = _compile_optional(include_regex)
        self.exclude_re = _compile_optional(exclude_regex)
        self.limiter = limiter or RateLimiter(max_bytes_per_min)
        self.spill_path = Path(spill_path) if spill_path else self.state_path.parent / "spill.log"
        self.alert_patterns = [re.compile(p) for p in (alert_patterns or [])]
        self.dropped = 0
        self.rate_limited = False
        self._reader = reader or journalctl_read
        self._state = _load_json(self.state_path)

    def collect(self) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        events: List[Dict[str, Any]] = []
        alerts: List[Dict[str, Any]] = []
        self.rate_limited = False
        cursor = self._state.get("journald_cursor")
        first = not cursor
        records, new_cursor = self._reader(cursor, self.units, 1 if first else self.max_entries)
        if first:
            # Seed cursor from the newest entry; do not dump the whole journal.
            if new_cursor:
                self._state["journald_cursor"] = new_cursor
                self._persist_cursor(new_cursor)
            return [], []
        for rec in records:
            event = journald_record_to_event(rec)
            admitted = self._admit(event, event.get("message") or "")
            if admitted is None:
                continue
            events.append(admitted)
            alerts.extend(self._pattern_alerts(admitted))
        if new_cursor:
            self._state["journald_cursor"] = new_cursor
            self._persist_cursor(new_cursor)
        return events, alerts

    def _persist_cursor(self, cursor: str) -> None:
        """Écrit uniquement le curseur journald.

        Le fichier d'état est partagé avec le collecteur de fichiers. Le code
        précédent fusionnait `self._state` — un instantané pris à la
        *construction* — dans le contenu relu du disque, réécrivant donc des
        positions de fichiers périmées et **faisant reculer** les offsets : au
        redémarrage, des lignes déjà expédiées l'étaient de nouveau. Seule la
        clé de ce collecteur doit être touchée.
        """
        merged = _load_json(self.state_path)
        merged["journald_cursor"] = cursor
        _save_json(self.state_path, merged)


def winevt_level(level: Any) -> str:
    try:
        return WIN_LEVEL.get(int(level), "info")
    except (TypeError, ValueError):
        name = str(level or "info").lower()
        if "crit" in name:
            return "critical"
        if "err" in name:
            return "error"
        if "warn" in name:
            return "warning"
        if "verb" in name or "debug" in name:
            return "debug"
        return "info"


def _powershell_exe() -> str:
    system_root = os.environ.get("SystemRoot", r"C:\Windows")
    return str(Path(system_root) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe")


def winevt_bookmark_powershell(channel: str) -> int:
    script = (
        f"$e = Get-WinEvent -LogName {json.dumps(channel)} -MaxEvents 1 "
        "-ErrorAction SilentlyContinue | Select-Object -First 1; "
        "if ($e) { $e.RecordId } else { 0 }"
    )
    try:
        proc = subprocess.run(
            [_powershell_exe(), "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return 0
    text = (proc.stdout or "").strip()
    try:
        return int(text.splitlines()[-1]) if text else 0
    except (ValueError, IndexError):
        return 0


def winevt_read_powershell(channel: str, after_id: int, limit: int) -> List[Dict[str, Any]]:
    xpath = f"*[System[EventRecordID > {int(after_id)}]]"
    script = (
        f"$events = Get-WinEvent -LogName {json.dumps(channel)} "
        f"-FilterXPath {json.dumps(xpath)} -MaxEvents {int(limit)} -Oldest "
        "-ErrorAction SilentlyContinue; "
        "foreach ($e in $events) { "
        "[ordered]@{ RecordId = $e.RecordId; "
        "TimeCreated = $e.TimeCreated.ToUniversalTime().ToString('o'); "
        "Level = $e.Level; ProviderName = [string]$e.ProviderName; "
        "Id = $e.Id; Message = [string]$e.Message; Channel = "
        f"{json.dumps(channel)} "
        "} | ConvertTo-Json -Compress -Depth 3 }"
    )
    try:
        proc = subprocess.run(
            [_powershell_exe(), "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=45,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return []
    rows: List[Dict[str, Any]] = []
    for line in (proc.stdout or "").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict):
            rows.append(rec)
    return rows


def winevt_read_pywin32(channel: str, after_id: int, limit: int) -> List[Dict[str, Any]]:
    import win32evtlog  # type: ignore
    import win32evtlogutil  # type: ignore

    handle = win32evtlog.OpenEventLog(None, channel)
    flags = win32evtlog.EVENTLOG_FORWARDS_READ | win32evtlog.EVENTLOG_SEQUENTIAL_READ
    rows: List[Dict[str, Any]] = []
    try:
        if after_id > 0:
            try:
                win32evtlog.ReadEventLog(
                    handle,
                    win32evtlog.EVENTLOG_SEEK_READ | win32evtlog.EVENTLOG_FORWARDS_READ,
                    after_id,
                )
            except Exception:
                pass
        while len(rows) < limit:
            batch = win32evtlog.ReadEventLog(handle, flags, 0)
            if not batch:
                break
            for ev in batch:
                rec_id = int(getattr(ev, "RecordNumber", 0) or 0)
                if rec_id <= after_id:
                    continue
                try:
                    message = win32evtlogutil.SafeFormatMessage(ev, channel) or ""
                except Exception:
                    inserts = getattr(ev, "StringInserts", None) or []
                    message = " ".join(str(x) for x in inserts)
                event_type = int(getattr(ev, "EventType", 4) or 4)
                level = {1: 2, 2: 3, 4: 4}.get(event_type, 4)
                generated = getattr(ev, "TimeGenerated", None)
                if generated is not None:
                    ts = generated.replace(tzinfo=timezone.utc).isoformat() if generated.tzinfo is None else generated.isoformat()
                else:
                    ts = _now().isoformat()
                rows.append(
                    {
                        "RecordId": rec_id,
                        "TimeCreated": ts,
                        "Level": level,
                        "ProviderName": str(getattr(ev, "SourceName", "") or ""),
                        "Id": int(getattr(ev, "EventID", 0) or 0) & 0xFFFF,
                        "Message": message,
                        "Channel": channel,
                    }
                )
                if len(rows) >= limit:
                    break
    finally:
        win32evtlog.CloseEventLog(handle)
    return rows


def default_winevt_read(channel: str, after_id: int, limit: int) -> List[Dict[str, Any]]:
    try:
        return winevt_read_pywin32(channel, after_id, limit)
    except Exception:
        return winevt_read_powershell(channel, after_id, limit)


def winevt_record_to_event(rec: Dict[str, Any]) -> Dict[str, Any]:
    ts = rec.get("TimeCreated") or _now().isoformat()
    channel = str(rec.get("Channel") or rec.get("LogName") or "Application")
    provider = str(rec.get("ProviderName") or "")
    event_id = rec.get("Id", "")
    message = str(rec.get("Message") or "")
    prefix = f"{provider}[{event_id}] " if provider or event_id != "" else ""
    return {
        "ts": str(ts),
        "severity": winevt_level(rec.get("Level") or rec.get("LevelDisplayName")),
        "message": prefix + message,
        "parsed": True,
        "raw": message,
        "source": "winevt",
        "channel": channel,
        "record_id": rec.get("RecordId"),
    }


class WinEventLogCollector(_FilterMixin):
    """Windows Event Log (System/Application + custom channels) — AGT-031."""

    def __init__(
        self,
        state_path: str | Path,
        channels: Optional[List[str]] = None,
        max_entries: int = 200,
        severity_floor: str = "debug",
        include_regex: Optional[str] = None,
        exclude_regex: Optional[str] = None,
        max_bytes_per_min: int = 5 * 1024 * 1024,
        spill_path: Optional[str | Path] = None,
        alert_patterns: Optional[List[str]] = None,
        limiter: Optional[RateLimiter] = None,
        reader: Optional[WinEvtReader] = None,
        bookmarker: Optional[WinEvtBookmark] = None,
    ) -> None:
        self.state_path = Path(state_path)
        self.channels = channels or ["System", "Application"]
        self.max_entries = max_entries
        self.severity_floor = severity_floor.lower()
        self.include_re = _compile_optional(include_regex)
        self.exclude_re = _compile_optional(exclude_regex)
        self.limiter = limiter or RateLimiter(max_bytes_per_min)
        self.spill_path = Path(spill_path) if spill_path else self.state_path.parent / "spill.log"
        self.alert_patterns = [re.compile(p) for p in (alert_patterns or [])]
        self.dropped = 0
        self.rate_limited = False
        self._reader = reader or default_winevt_read
        self._bookmarker = bookmarker or winevt_bookmark_powershell
        self._state = _load_json(self.state_path)
        self._bookmarks: Dict[str, int] = {
            k.replace("winevt:", ""): int(v)
            for k, v in self._state.items()
            if k.startswith("winevt:") and str(v).isdigit()
        }

    def collect(self) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        events: List[Dict[str, Any]] = []
        alerts: List[Dict[str, Any]] = []
        self.rate_limited = False
        for channel in self.channels:
            after_id = self._bookmarks.get(channel)
            if after_id is None:
                after_id = int(self._bookmarker(channel) or 0)
                self._bookmarks[channel] = after_id
                continue
            try:
                rows = self._reader(channel, after_id, self.max_entries)
            except Exception:
                continue
            max_seen = after_id
            for rec in rows:
                try:
                    rec_id = int(rec.get("RecordId") or 0)
                except (TypeError, ValueError):
                    rec_id = 0
                if rec_id > max_seen:
                    max_seen = rec_id
                event = winevt_record_to_event(rec)
                admitted = self._admit(event, event.get("message") or "")
                if admitted is None:
                    continue
                events.append(admitted)
                alerts.extend(self._pattern_alerts(admitted))
            self._bookmarks[channel] = max_seen
        merged = _load_json(self.state_path)
        for channel, rec_id in self._bookmarks.items():
            merged[f"winevt:{channel}"] = rec_id
        _save_json(self.state_path, merged)
        self._state = merged
        return events, alerts


def _flag_enabled(value: Any, default_os: bool) -> bool:
    if value is True or value == "true":
        return True
    if value is False or value == "false":
        return False
    return default_os  # auto / missing


class CombinedLogCollector:
    """Fan-in of file + journald + Windows Event Log with a shared 5 MB/min cap."""

    def __init__(self, sources: List[Any]) -> None:
        self.sources = sources
        self.dropped = 0
        self.rate_limited = False

    @classmethod
    def from_config(cls, cfg: Dict[str, Any]) -> Optional["CombinedLogCollector"]:
        if not cfg.get("enabled"):
            return None
        offset_path = Path(cfg.get("offset_path", "data/agent-buffer/log-offsets.json"))
        spill_path = cfg.get("spill_path", "data/agent-buffer/log-spill.log")
        limiter = RateLimiter(int(cfg.get("max_bytes_per_min", 5 * 1024 * 1024)))
        common = dict(
            severity_floor=cfg.get("severity_floor", "debug"),
            include_regex=cfg.get("include_regex"),
            exclude_regex=cfg.get("exclude_regex"),
            spill_path=spill_path,
            alert_patterns=cfg.get("alert_patterns") or [],
            limiter=limiter,
        )
        sources: List[Any] = []
        patterns = cfg.get("files") or []
        if isinstance(patterns, list) and patterns and isinstance(patterns[0], dict):
            patterns = [p.get("glob") or p.get("path") for p in patterns if p.get("glob") or p.get("path")]
        patterns = [p for p in patterns if p]
        if patterns:
            sources.append(
                FileLogCollector(
                    patterns=patterns,
                    offset_path=offset_path,
                    parser=cfg.get("parser", "raw"),
                    multiline_start=cfg.get("multiline_start"),
                    **common,
                )
            )
        system = platform.system().lower()
        jcfg = cfg.get("journald") or {}
        if _flag_enabled(jcfg.get("enabled", "auto"), system == "linux"):
            sources.append(
                JournaldCollector(
                    state_path=offset_path,
                    units=jcfg.get("units") or [],
                    max_entries=int(jcfg.get("max_entries", 200)),
                    **common,
                )
            )
        wcfg = cfg.get("winevt") or {}
        if _flag_enabled(wcfg.get("enabled", "auto"), system == "windows"):
            sources.append(
                WinEventLogCollector(
                    state_path=offset_path,
                    channels=wcfg.get("channels") or ["System", "Application"],
                    max_entries=int(wcfg.get("max_entries", 200)),
                    **common,
                )
            )
        if not sources:
            return None
        return cls(sources)

    def collect(self) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        events: List[Dict[str, Any]] = []
        alerts: List[Dict[str, Any]] = []
        self.dropped = 0
        self.rate_limited = False
        for source in self.sources:
            try:
                ev, al = source.collect()
            except Exception:
                continue
            events.extend(ev)
            alerts.extend(al)
            self.dropped += int(getattr(source, "dropped", 0) or 0)
            if getattr(source, "rate_limited", False):
                self.rate_limited = True
        return events, alerts
