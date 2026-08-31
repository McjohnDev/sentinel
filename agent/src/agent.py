import psutil
import socket
import platform
import uuid
import time
import requests
from datetime import datetime, timezone
import json
import yaml
import os
import logging
import sys
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Dict, Any, List, Optional

# Repo root (shared.*) and agent/src (plugins.*) on sys.path.
# Local: agent/src/agent.py → repo. Docker: /app/src/agent.py → /app (shared/).
_AGENT_SRC = Path(__file__).resolve().parent
_REPO_ROOT = next(
    (p for p in [_AGENT_SRC, *_AGENT_SRC.parents] if (p / "shared").is_dir()),
    _AGENT_SRC.parent,
)
for _p in (str(_REPO_ROOT), str(_AGENT_SRC)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from instance_lock import InstanceLock, InstanceLockError  # noqa: E402
from durable_buffer import DurableBuffer  # noqa: E402
from task_handler import handle_incoming_tasks  # noqa: E402
from log_collector import CombinedLogCollector  # noqa: E402
from disk_metrics import collect_disk_partitions  # noqa: E402
from remote_config import RemoteConfigState, deep_merge  # noqa: E402
from session_state import SessionState  # noqa: E402
from runtime_info import collect_runtime_info  # noqa: E402
from agent_paths import machine_id_path, resolve_buffer_dir  # noqa: E402


_SELF_PROC: Optional[psutil.Process] = None


def _self_process() -> psutil.Process:
    """Handle de processus mémorisé.

    cpu_percent(interval=None) mesure l'écart depuis l'appel précédent sur le
    *même* objet Process : le recréer à chaque mesure renverrait toujours 0.0.
    """
    global _SELF_PROC
    if _SELF_PROC is None or _SELF_PROC.pid != os.getpid():
        _SELF_PROC = psutil.Process(os.getpid())
        _SELF_PROC.cpu_percent(interval=None)  # amorce la référence
    return _SELF_PROC


def _measure_agent_footprint() -> Dict[str, float]:
    """AGT-007 — empreinte CPU/RAM de l'agent sur son hôte.

    La forme bloquante cpu_percent(interval=0.05) diffusait les compteurs de
    part et d'autre d'un sleep exécuté par l'unique thread de l'agent : on
    mesurait donc l'agent pendant qu'il dormait. Le travail réel tombait hors
    fenêtre (lecture ~0.0) tandis qu'un seul tick d'ordonnanceur atterrissant
    dans les 50 ms se lisait ~20-30%, rendant le budget de 2% inobservable.

    La forme non bloquante couvre tout l'intervalle de heartbeat : elle capte
    le travail réel et amortit le bruit d'ordonnancement.

    La valeur est **ramenée à la machine entière**. `Process.cpu_percent()`
    de psutil s'exprime par rapport à *un* cœur et peut donc dépasser 100 %,
    alors qu'un budget de 2 % se lit comme une part de l'hôte. Sans cette
    normalisation, l'empreinte était multipliée par le nombre de cœurs : sur
    un poste à 8 cœurs, un agent consommant réellement 3 % de la machine se
    déclarait à 26 % et déclenchait une alerte de dépassement à chaque
    collecte.
    """
    proc = _self_process()
    try:
        with proc.oneshot():
            cpu = float(proc.cpu_percent(interval=None))
            ram_mb = float(proc.memory_info().rss) / (1024 * 1024)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        # L'auto-surveillance ne doit jamais interrompre une collecte.
        return {"cpu_percent": 0.0, "ram_mb": 0.0}

    cores = psutil.cpu_count(logical=True) or 1
    return {"cpu_percent": round(cpu / cores, 2), "ram_mb": round(ram_mb, 2)}


class CBCAgent:
    """Agent de supervision CBC."""
    
    def __init__(self, config_path: str = None, server_url: str = None, enrollment_token: str = None):
        self.config_path = config_path
        base = self._load_config(config_path) if config_path else {}
        degraded_preview = base.get("degraded_mode") or {}
        buffer_dir = resolve_buffer_dir(
            degraded_preview.get("buffer_dir", "data/agent-buffer"), config_path
        )
        self._remote = RemoteConfigState(buffer_dir / "remote-config.yaml")
        self.config = deep_merge(base, self._remote.load_overlay())
        
        # Priorité: config YAML > arguments > valeurs par défaut
        self.server_url = self.config.get('server', {}).get('url', server_url or "https://localhost:8443")
        self.enrollment_token = self.config.get('server', {}).get('enrollment_token', enrollment_token or "demo-token-123")
        
        self.agent_id = None
        self.auth_key = None
        self.machine_id = self._get_or_generate_machine_id()
        
        agent_config = self.config.get('agent', {})
        self.heartbeat_interval = agent_config.get('heartbeat_interval', 30)
        self.ping_interval = int(agent_config.get('ping_interval', 10))
        self.retry_interval = agent_config.get('retry_interval', 60)
        self.max_retries = agent_config.get('max_retries', 3)
        
        self.metrics_config = self.config.get('metrics', {})
        self.degraded_mode_config = self.config.get('degraded_mode', {})
        self.logging_config = self.config.get('logging', {})
        
        self.heartbeat_buffer = []  # legacy in-memory (kept as fallback)
        self.retries = 0
        #: Dernière erreur de liaison, remontée dans le bloc d'exécution pour
        #: qu'un exploitant la voie depuis la plateforme sans ouvrir de
        #: session sur l'hôte.
        self._last_error: Optional[str] = None
        #: Demande d'arrêt propre. Sans elle, `run()` était une boucle
        #: infinie qu'on ne pouvait interrompre qu'en tuant le processus :
        #: le gestionnaire de services Windows aurait signalé un échec
        #: d'arrêt, et le tampon en cours d'écriture aurait pu être tronqué.
        self._stop = threading.Event()
        self._plugin_registry = None
        server_cfg = self.config.get("server", {})
        # Production default: verify TLS. Local docker HTTP / self-signed lab: set tls_verify: false
        self.tls_verify = bool(server_cfg.get("tls_verify", True))
        degraded = self.config.get("degraded_mode", {})
        buffer_dir = resolve_buffer_dir(
            degraded.get("buffer_dir", "data/agent-buffer"), self.config_path
        )
        max_mb = int(degraded.get("max_size_mb", 500))
        max_hours = int(degraded.get("max_age_hours", 24))
        self._durable = DurableBuffer(
            buffer_dir / "queue.jsonl",
            max_bytes=max_mb * 1024 * 1024,
            max_age_seconds=max_hours * 3600,
        )
        self._session = SessionState(buffer_dir / "session.json")
        saved = self._session.load()
        if saved.get("auth_key") and saved.get("machine_id") == self.machine_id:
            self.auth_key = saved.get("auth_key")
            self.agent_id = saved.get("agent_id")
        
        # Configuration du logging
        self._setup_logging()
        self._init_plugins()
        self._init_logs()
        if self._remote.version:
            self.logger.info("Remote config overlay active version=%s", self._remote.version)

    def _init_plugins(self) -> None:
        """Load Lot-1 plugin registry (FS1). Falls back silently if unavailable."""
        try:
            from plugins import build_default_registry

            self._plugin_registry = build_default_registry()
            names = [m.name for m in self._plugin_registry.list_manifests()]
            self.logger.info("Plugins chargés: %s", ", ".join(names) if names else "(aucun)")
        except Exception as exc:
            # logger may not exist yet if called before _setup_logging in older paths
            if hasattr(self, "logger"):
                self.logger.warning("Plugins non chargés: %s", exc)
            self._plugin_registry = None

    def _init_logs(self) -> None:
        cfg = dict(self.config.get("logs") or {})
        # Mêmes ancrages que le tampon : `offset_path` et `spill_path` sont
        # relatifs dans la configuration livrée. Résolus depuis le répertoire
        # courant, ils suivaient l'endroit d'où l'agent avait été lancé — et
        # sous un service, ils auraient atterri dans System32. Un décalage de
        # position de lecture perdu, c'est un journal relu depuis le début ou
        # des lignes sautées.
        for key in ("offset_path", "spill_path"):
            value = cfg.get(key)
            if value:
                cfg[key] = str(resolve_buffer_dir(str(value), self.config_path))
        self._log_collector = None
        try:
            self._log_collector = CombinedLogCollector.from_config(cfg)
            if self._log_collector:
                names = [type(s).__name__ for s in self._log_collector.sources]
                self.logger.info("Log collector enabled sources=%s", ", ".join(names))
        except Exception as exc:
            self.logger.warning("Log collector not started: %s", exc)
            self._log_collector = None

    def send_logs(self) -> bool:
        if not self._log_collector or not self.auth_key:
            return True
        events, alerts = self._log_collector.collect()
        if self._log_collector.rate_limited:
            self.logger.warning("Log rate limit hit (AGT-038); spilled locally")
        if not events:
            return True
        try:
            resp = requests.post(
                f"{self.server_url}/api/ingest/logs",
                json={
                    "host": self._get_hostname(),
                    "events": events,
                    "dropped": self._log_collector.dropped,
                    "rate_limited": self._log_collector.rate_limited,
                    "pattern_alerts": alerts,
                },
                headers={"Authorization": self.auth_key},
                **self._http_kwargs(),
            )
            if resp.status_code == 200:
                self.logger.info("logs shipped count=%s", len(events))
                return True
            self.logger.error("log ingest failed: %s %s", resp.status_code, resp.text)
            return False
        except Exception as exc:
            self.logger.error("log ingest error: %s", exc)
            return False

    def _host_facts(self) -> Dict[str, Any]:
        """Caractéristiques matérielles constatées de l'hôte.

        Envoyées à l'enrôlement *et* à chaque battement : elles n'étaient
        déclarées qu'une fois, si bien qu'un ajout de mémoire ou une montée
        de version d'OS n'apparaissait jamais dans l'inventaire.
        """
        facts: Dict[str, Any] = {}
        try:
            facts["cpu_cores"] = psutil.cpu_count(logical=True)
            facts["ram_total_gb"] = round(psutil.virtual_memory().total / (1024 ** 3), 2)
        except Exception:
            pass
        try:
            _, disks = collect_disk_partitions(
                (self.metrics_config.get("disk") or {}) if isinstance(self.metrics_config, dict) else {}
            )
            total = sum(float(d.get("total_gb") or 0) for d in disks)
            if total:
                facts["disk_total_gb"] = round(total, 2)
        except Exception:
            pass
        return facts

    def _runtime_block(self) -> Dict[str, Any]:
        """Descriptif « où et comment je tourne », destiné à la fiche d'hôte."""
        try:
            plugins = []
            if self._plugin_registry:
                # `list_manifests()` rend des modèles PluginManifestV1, pas des
                # dictionnaires : les traiter comme tels faisait échouer tout
                # le bloc d'exécution, et l'erreur restait invisible.
                plugins = [getattr(m, "name", None) for m in self._plugin_registry.list_manifests()]
            return collect_runtime_info(
                config_path=self.config_path,
                server_url=self.server_url,
                tls_verify=self.tls_verify,
                agent_version=self._get_agent_version(),
                buffer_records=len(self._durable),
                last_error=self._last_error,
                plugins=[p for p in plugins if p],
            )
        except Exception as exc:
            # Un descriptif d'affichage ne doit jamais empêcher un battement.
            self.logger.debug("runtime introspection failed: %s", exc)
            return {}

    def _http_kwargs(self) -> dict:
        kwargs = {"timeout": 10, "verify": self.tls_verify}
        if not self.tls_verify:
            try:
                import urllib3
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            except Exception:
                pass
        return kwargs

    def _persist_session(self, *, last_error: Optional[str] = None, connected: bool = False) -> None:
        self._last_error = None if connected else (last_error or self._last_error)
        try:
            self._session.save(
                server_url=self.server_url,
                machine_id=self.machine_id,
                agent_id=self.agent_id,
                auth_key=self.auth_key,
                last_error=last_error,
                consecutive_failures=self.retries,
                buffer_records=len(self._durable),
                connected=connected,
            )
        except OSError as exc:
            if hasattr(self, "logger"):
                self.logger.warning("session.json write failed: %s", exc)

    #: Au-delà, l'écart d'horloge fausse les fenêtres de persistance des
    #: alertes et mérite un avertissement dans le journal de l'agent.
    CLOCK_SKEW_WARN_SECONDS = 120

    #: Codes signifiant « la plateforme ne connaît plus cette identité ».
    #: 404/410 comptent : si l'agent a été supprimé de l'inventaire côté
    #: serveur, rejouer la même clé indéfiniment laisse l'hôte invisible —
    #: c'est un ré-enrôlement qu'il faut, pas une nouvelle tentative.
    IDENTITY_LOST_STATUSES = (401, 403, 404, 410)

    def _post(self, path: str, payload: Optional[dict] = None, *, auth: bool = True):
        """POST JSON. Returns (response|None, 'ok'|'auth'|'fail')."""
        headers = {}
        if auth:
            if not self.auth_key:
                return None, "auth", "missing auth_key"
            headers["Authorization"] = self.auth_key
        try:
            resp = requests.post(
                f"{self.server_url}{path}",
                json=payload if payload is not None else {},
                headers=headers,
                **self._http_kwargs(),
            )
        except Exception as exc:
            return None, "fail", str(exc)
        if 200 <= resp.status_code < 300:
            return resp, "ok", None
        if resp.status_code in self.IDENTITY_LOST_STATUSES or self._reenroll_requested(resp):
            return resp, "auth", f"HTTP {resp.status_code} {resp.text[:200]}"
        return resp, "fail", f"HTTP {resp.status_code} {resp.text[:300]}"

    @staticmethod
    def _reenroll_requested(resp) -> bool:
        """La plateforme demande-t-elle explicitement un ré-enrôlement ?

        En-tête `X-CBC-Reenroll` ou corps `{"code": "agent_unknown"}`. Couvre
        le cas d'un 5xx transitoire suivi d'un vrai rejet d'identité.
        """
        try:
            if resp.headers.get("X-CBC-Reenroll"):
                return True
        except Exception:
            pass
        try:
            body = resp.json()
        except Exception:
            return False
        detail = body.get("detail") if isinstance(body, dict) else None
        if isinstance(detail, dict):
            return detail.get("code") == "agent_unknown" or detail.get("action") == "re_enroll"
        return False

    def _forget_identity(self, reason: str) -> None:
        """Oublie la session serveur pour repartir sur un enrôlement propre.

        L'agent_id était conservé après un rejet d'authentification : il
        pointait alors vers une ligne qui n'existe plus, et les points de
        métrique bufferisés continuaient d'être étiquetés avec.
        """
        self.logger.warning("Identité plateforme perdue (%s) — ré-enrôlement", reason)
        self.auth_key = None
        self.agent_id = None

    def send_ping(self) -> str:
        resp, status, err = self._post("/api/agents/ping", {})
        if status == "ok":
            self.retries = 0
            self._persist_session(connected=True)
            return "ok"
        if status == "auth":
            self._forget_identity(err or "ping refusé")
            self._persist_session(last_error=err or "auth", connected=False)
            return "auth"
        self.retries += 1
        self.logger.warning("Ping failed: %s", err)
        self._persist_session(last_error=err, connected=False)
        return "fail"

    def _buffer_cycle(self) -> None:
        if not self.degraded_mode_config.get("enabled", True):
            return
        try:
            metrics = self.collect_metrics()
            self._durable.enqueue("heartbeat", metrics)
            plugin_payload = self.collect_plugin_metrics()
            if plugin_payload:
                self._durable.enqueue("metrics", plugin_payload)
            self.logger.info(
                "Buffered on disk records=%s size=%s bytes",
                len(self._durable),
                self._durable.size_bytes(),
            )
        except Exception as exc:
            self.logger.error("buffer cycle failed: %s", exc)

    def _process_echo(self, echo: dict) -> None:
        """Exploite l'écho de présence renvoyé par la plateforme (point 5).

        Trois choses que l'agent ne peut pas constater seul : que le serveur
        l'a bien reconnu sous cette identité, si son horloge dérive, et s'il
        sort d'une coupure. La dernière compte : un rattrapage de tampon
        silencieux ressemble à un fonctionnement normal dans les journaux,
        alors que c'est le moment où l'on veut savoir ce qui a été perdu.
        """
        if not isinstance(echo, dict):
            return

        remote_id = echo.get("agent_id")
        if remote_id and self.agent_id and remote_id != self.agent_id:
            # La plateforme nous connaît sous une autre identité que la nôtre.
            self.logger.warning(
                "Identité divergente : la plateforme répond %s, l'agent porte %s",
                remote_id,
                self.agent_id,
            )
            self.agent_id = remote_id

        skew = echo.get("clock_skew_seconds")
        if isinstance(skew, int) and abs(skew) > self.CLOCK_SKEW_WARN_SECONDS:
            # Une horloge décalée fausse les fenêtres de persistance des
            # alertes : le symptôme est une alerte qui ne se déclenche jamais.
            self.logger.warning(
                "Horloge locale décalée de %ss par rapport à la plateforme", skew,
            )

        if echo.get("resumed_after_outage"):
            self.logger.warning(
                "Reprise de contact après %ss d'indisponibilité — rattrapage de %s enregistrement(s)",
                echo.get("previous_gap_seconds"),
                len(self._durable),
            )

    def _process_heartbeat_response(self, body: dict) -> None:
        """Handle config push (AGT-008) and L0-reject any task.v1 (AGT-010)."""
        self._process_echo(body.get("echo") or {})
        config_push = body.get("config")
        if isinstance(config_push, dict) and config_push.get("version") is not None:
            try:
                self._apply_remote_config(int(config_push["version"]), config_push.get("payload") or {})
            except Exception as exc:
                self.logger.error("remote config apply failed: %s", exc)
        tasks = body.get("tasks") or []
        if not tasks:
            return
        try:
            level = str((self.config.get("agent") or {}).get("capability_level") or "L0")
            results = handle_incoming_tasks(tasks, capability_level=level)
        except Exception as exc:
            self.logger.error("task.v1 parse/exec failed: %s", exc)
            return
        try:
            resp = requests.post(
                f"{self.server_url}/api/agents/tasks/results",
                json={"results": results},
                headers={"Authorization": self.auth_key},
                **self._http_kwargs(),
            )
            self.logger.info("task results posted count=%s status=%s", len(results), resp.status_code)
        except Exception as exc:
            self.logger.error("task result post failed: %s", exc)

    def _apply_remote_config(self, version: int, payload: Dict[str, Any]) -> None:
        """Merge platform config overlay and ack version (AGT-008)."""
        if version <= self._remote.version:
            return
        overlay = self._remote.apply(version, payload if isinstance(payload, dict) else {})
        base = self._load_config(self.config_path) if self.config_path else {}
        self.config = deep_merge(base, overlay)
        agent_config = self.config.get("agent") or {}
        self.heartbeat_interval = agent_config.get("heartbeat_interval", self.heartbeat_interval)
        if agent_config.get("ping_interval"):
            self.ping_interval = int(agent_config.get("ping_interval"))
        self.metrics_config = self.config.get("metrics", {})
        self.degraded_mode_config = self.config.get("degraded_mode", {})
        self._init_logs()
        self.logger.info("Applied remote config version=%s keys=%s", version, list(overlay.keys()))
        try:
            resp = requests.post(
                f"{self.server_url}/api/agents/config/ack",
                json={"version": version},
                headers={"Authorization": self.auth_key},
                **self._http_kwargs(),
            )
            self.logger.info("config ack version=%s status=%s", version, resp.status_code)
        except Exception as exc:
            self.logger.error("config ack failed: %s", exc)

    def collect_plugin_metrics(self) -> List[dict]:
        """Collect metric.v1 points via plugin registry."""
        if not self._plugin_registry or not self.agent_id:
            return []
        svc = self.config.get("services_monitoring") or {}
        files = self.config.get("files_monitoring") or {}
        context = {
            "agent_id": self.agent_id,
            "hostname": self._get_hostname(),
            "watched_processes": self.config.get("metrics", {}).get("processes", {}).get("watched", []),
            "watched_services": svc.get("services") or [],
            "watched_files": files.get("files") or [],
        }
        metrics = self._plugin_registry.collect_all(context)
        return [m.to_wire_dict() for m in metrics]

    def send_plugin_metrics(self) -> bool:
        """POST plugin metrics to canonical ingest endpoint (FS1)."""
        payload = self.collect_plugin_metrics()
        if not payload or not self.auth_key:
            return False
        try:
            response = requests.post(
                f"{self.server_url}/api/ingest/metrics",
                json={"metrics": payload},
                headers={"Authorization": self.auth_key},
                **self._http_kwargs(),
            )
            if response.status_code == 200:
                body = response.json()
                self.logger.info(
                    "metric.v1 ingest ok accepted=%s rejected=%s",
                    body.get("accepted"),
                    body.get("rejected"),
                )
                return True
            self.logger.error("metric.v1 ingest failed: %s %s", response.status_code, response.text)
            return False
        except Exception as exc:
            self.logger.error("metric.v1 ingest error: %s", exc)
            return False
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Charge la configuration depuis un fichier YAML."""
        if not config_path or not os.path.exists(config_path):
            return {}
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            print(f"Erreur lors du chargement de la configuration: {e}")
            return {}
    
    def _setup_logging(self):
        """Configure le logging avec rotation."""
        log_level = self.logging_config.get('level', 'INFO')
        log_file = self.logging_config.get('file', 'agent.log')
        
        self.logger = logging.getLogger('CBCAgent')
        self.logger.setLevel(getattr(logging, log_level))
        
        # Handler console
        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, log_level))
        console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        # Handler fichier avec rotation
        rotation_config = self.logging_config.get('rotation', {})
        if rotation_config.get('enabled', True):
            max_size = rotation_config.get('max_size_mb', 10) * 1024 * 1024
            backup_count = rotation_config.get('backup_count', 5)
            
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=max_size,
                backupCount=backup_count
            )
            file_handler.setLevel(getattr(logging, log_level))
            file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            file_handler.setFormatter(file_formatter)
            self.logger.addHandler(file_handler)
        
    def _get_or_generate_machine_id(self) -> str:
        """Génère ou récupère le Machine ID persistant."""
        path = machine_id_path()
        try:
            if path.exists():
                stored = path.read_text(encoding="utf-8").strip()
                if stored:
                    return stored
        except OSError:
            pass
        machine_id = str(uuid.uuid4())
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(machine_id, encoding="utf-8")
        except OSError:
            pass
        return machine_id
    
    def _get_hostname(self) -> str:
        """Récupère le nom de la machine."""
        return socket.gethostname()
    
    def _get_ip_address(self) -> str:
        """Récupère l'adresse IP principale."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"
    
    def _get_os_info(self) -> tuple:
        """Récupère les informations sur l'OS."""
        return platform.system(), platform.release()
    
    def _get_agent_version(self) -> str:
        """Version de l'agent."""
        return "1.1.0"
    
    def collect_metrics(self) -> dict:
        """Collecte toutes les métriques système."""
        # CPU
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_cores = psutil.cpu_count(logical=True)
        
        # RAM
        ram = psutil.virtual_memory()
        ram_percent = ram.percent
        ram_total_gb = ram.total / (1024**3)
        ram_used_gb = ram.used / (1024**3)
        ram_free_gb = ram.available / (1024**3)
        
        disk_cfg = (self.metrics_config.get("disk") or {}) if isinstance(self.metrics_config, dict) else {}
        disk_summary, disks = collect_disk_partitions(disk_cfg if disk_cfg.get("enabled", True) else {"path": disk_cfg.get("path")})

        # Uptime
        uptime_seconds = int(time.time() - psutil.boot_time())
        
        # Services et fichiers (si configurés)
        services_data = self.collect_services()
        files_data = self.collect_files()
        footprint = _measure_agent_footprint()
        reported_os, reported_os_version = self._get_os_info()
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "cpu_percent": cpu_percent,
            "cpu_cores": cpu_cores,
            "ram_percent": ram_percent,
            "ram_total_gb": round(ram_total_gb, 2),
            "ram_used_gb": round(ram_used_gb, 2),
            "ram_free_gb": round(ram_free_gb, 2),
            "disk_percent": disk_summary["disk_percent"],
            "disk_total_gb": disk_summary["disk_total_gb"],
            "disk_used_gb": disk_summary["disk_used_gb"],
            "disk_free_gb": disk_summary["disk_free_gb"],
            "disk_mount": disk_summary.get("disk_mount"),
            "disks": disks,
            "ip_address": self._get_ip_address(),
            "uptime_seconds": uptime_seconds,
            "services": services_data,
            "files": files_data,
            "config_version": self._remote.version,
            "agent_cpu_percent": footprint["cpu_percent"],
            "agent_ram_mb": footprint["ram_mb"],
            # Facteurs système redéclarés : l'inventaire doit décrire la
            # machine telle qu'elle est, pas telle qu'elle était le jour de
            # son installation.
            "hostname": self._get_hostname(),
            "os": reported_os,
            "os_version": reported_os_version,
            "agent_version": self._get_agent_version(),
            **self._host_facts(),
            "runtime": self._runtime_block(),
        }
    
    def collect_services(self) -> list:
        """Collecte l'état des services système (liste CBC / remote config)."""
        from plugins.collectors.services import _service_status

        services_config = self.config.get('services_monitoring', {}) or {}
        if not services_config.get('enabled', True):
            return []
        services_to_monitor = services_config.get('services', []) or []
        services_data = []
        for service_name in services_to_monitor:
            name = service_name if isinstance(service_name, str) else str(service_name.get("name") or "")
            if not name:
                continue
            services_data.append({"name": name, "status": _service_status(name)})
        return services_data
    
    def collect_files(self) -> list:
        """Constate l'état des fichiers demandés par le plan de supervision.

        L'agent ne juge pas : il rapporte. C'est la plateforme qui confronte
        l'observation à la condition attendue (`must_exist` /
        `must_not_exist`), là où vivent le plan et l'historique.

        `exists` vaut `None` quand la vérification n'a pas abouti. La version
        précédente renvoyait `False` en cas d'erreur, rendant un fichier
        présent mais illisible indiscernable d'un fichier absent — bénin tant
        qu'on n'alertait que sur l'absence, trompeur dès lors qu'on alerte
        aussi sur la *présence*.
        """
        files_config = self.config.get('files_monitoring', {}) or {}
        if not files_config.get('enabled', True):
            return []
        files_to_monitor = files_config.get('files', []) or []
        files_data = []

        for entry in files_to_monitor:
            file_path = entry if isinstance(entry, str) else (entry or {}).get("path")
            if not file_path:
                continue
            try:
                stat = os.stat(file_path)
                files_data.append({
                    "path": file_path,
                    "exists": True,
                    "size_bytes": stat.st_size,
                    # UTC explicite : le reste du battement est en UTC, une
                    # heure locale ici fausserait toute comparaison.
                    "last_modified": datetime.fromtimestamp(
                        stat.st_mtime, tz=timezone.utc
                    ).isoformat(),
                })
            except FileNotFoundError:
                files_data.append({
                    "path": file_path,
                    "exists": False,
                    "size_bytes": None,
                    "last_modified": None,
                })
            except OSError as exc:
                # Droits insuffisants, chemin réseau injoignable, verrou…
                # On ne sait pas, et on le dit.
                self.logger.warning(
                    "Vérification impossible pour %s : %s", file_path, exc
                )
                files_data.append({
                    "path": file_path,
                    "exists": None,
                    "size_bytes": None,
                    "last_modified": None,
                    "error": str(exc)[:200],
                })

        return files_data

    def enroll(self) -> bool:
        """Enrôle l'agent auprès du serveur."""
        hostname = self._get_hostname()
        os_name, os_version = self._get_os_info()
        agent_version = self._get_agent_version()
        
        # Récupérer le type de machine depuis la configuration (défaut: workstation)
        machine_type = self.config.get('agent', {}).get('machine_type', 'workstation')
        
        # Récupérer la configuration de disponibilité
        availability_config = self.config.get('availability', {})
        
        payload = {
            "token": self.enrollment_token,
            "machine_id": self.machine_id,
            "hostname": hostname,
            "ip_address": self._get_ip_address(),
            "os": os_name,
            "os_version": os_version,
            "agent_version": agent_version,
            "machine_type": machine_type,
            "availability_config": availability_config,
            **self._host_facts(),
            "runtime": self._runtime_block(),
        }
        
        try:
            resp, status, err = self._post("/api/agents/enroll", payload, auth=False)
            if status == "ok" and resp is not None:
                data = resp.json()
                self.agent_id = data["agent_id"]
                self.auth_key = data["auth_key"]
                self.logger.info(f"Agent enregistré avec succès. ID: {self.agent_id}")
                self._persist_session(connected=True)
                return True
            self.logger.error("Erreur d'enrôlement: %s", err)
            self._persist_session(last_error=err or "enroll failed", connected=False)
            return False
        except Exception as e:
            self.logger.error(f"Erreur lors de l'enrôlement: {e}")
            self._persist_session(last_error=str(e), connected=False)
            return False
    
    def send_heartbeat(self) -> str:
        """Envoie un heartbeat au serveur. Returns ok|auth|fail."""
        if not self.auth_key:
            return "auth"

        metrics = self.collect_metrics()
        resp, status, err = self._post("/api/agents/heartbeat", metrics)
        if status == "ok" and resp is not None:
            self.logger.info(f"Heartbeat envoyé - CPU: {metrics['cpu_percent']}%, RAM: {metrics['ram_percent']}%")
            try:
                self._process_heartbeat_response(resp.json())
            except Exception:
                pass
            self._persist_session(connected=True)
            return "ok"
        if status == "auth":
            self._forget_identity(err or "heartbeat refusé")
            self._persist_session(last_error=err or "auth", connected=False)
            return "auth"
        self.logger.error("Erreur heartbeat: %s", err)
        self._persist_session(last_error=err, connected=False)
        return "fail"
    
    def request_stop(self) -> None:
        """Demande l'arrêt de la boucle à la prochaine occasion."""
        self._stop.set()

    def _pause(self, seconds: float) -> None:
        """Attente interruptible — rend la main aussitôt qu'un arrêt est demandé."""
        self._stop.wait(seconds)

    def run(self):
        """Boucle principale : ping de présence + heartbeat + reconnexion sans arrêt."""
        self.logger.info("Démarrage de l'agent CBC Supervision...")
        self.logger.info(f"Serveur: {self.server_url}")
        self.logger.info(f"Machine ID: {self.machine_id}")
        self.logger.info(
            "Ping=%ss heartbeat=%ss TLS verify=%s",
            self.ping_interval,
            self.heartbeat_interval,
            self.tls_verify,
        )
        if not self.tls_verify:
            self.logger.warning("TLS verification DISABLED — lab/self-signed only (AGT-003)")
        self.logger.info(
            "Mode dégradé: %s",
            "activé" if self.degraded_mode_config.get("enabled", True) else "désactivé",
        )

        enroll_backoff = 5.0
        next_enroll = 0.0
        next_ping = 0.0
        next_heartbeat = 0.0

        while not self._stop.is_set():
            now = time.monotonic()

            if not self.auth_key:
                if now >= next_enroll:
                    self.logger.info("Tentative d'enrôlement...")
                    if self.enroll():
                        enroll_backoff = 5.0
                        next_ping = now
                        next_heartbeat = now
                    else:
                        self.logger.error(
                            "Enrôlement impossible — nouvel essai dans %.0fs (l'agent reste actif)",
                            enroll_backoff,
                        )
                        self._buffer_cycle()
                        next_enroll = now + enroll_backoff
                        enroll_backoff = min(enroll_backoff * 2, 60.0)
                self._pause(1)
                continue

            if now >= next_ping:
                ping_status = self.send_ping()
                if ping_status == "auth":
                    next_enroll = 0.0
                    enroll_backoff = 5.0
                    self._pause(1)
                    continue
                next_ping = now + max(5, self.ping_interval)

            if now >= next_heartbeat:
                hb_status = self.send_heartbeat()
                if hb_status == "ok":
                    self.retries = 0
                    plugin_ok = self.send_plugin_metrics()
                    if not plugin_ok:
                        payload = self.collect_plugin_metrics()
                        if payload:
                            self._durable.enqueue("metrics", payload)
                    self.send_logs()
                    self._flush_durable()
                elif hb_status == "auth":
                    next_enroll = 0.0
                    enroll_backoff = 5.0
                    self._pause(1)
                    continue
                else:
                    self._buffer_cycle()
                next_heartbeat = now + max(10, self.heartbeat_interval)

            self._pause(1)

        self.logger.info("Arrêt demandé — boucle de supervision terminée")

    def _flush_durable(self) -> None:
        if not self.degraded_mode_config.get("retry_on_recovery", True):
            return
        # Prélèvement en deux temps : le lot est renommé, pas supprimé. Un
        # arrêt brutal pendant le rejeu laisse un fichier « en vol » que le
        # démarrage suivant réintègre, au lieu de perdre le lot entier.
        records = self._durable.checkout()
        if not records:
            return
        failed: List[dict] = []
        self.logger.info("Replaying %s buffered record(s)", len(records))
        try:
            for rec in records:
                kind = rec.get("kind")
                payload = rec.get("payload")
                ok = False
                if kind == "heartbeat":
                    ok = self._send_buffered_heartbeat(payload)
                elif kind == "metrics":
                    ok = self._send_buffered_metrics(payload)
                else:
                    # Type inconnu : ne pas le rejouer indéfiniment.
                    self.logger.warning("Enregistrement de type inconnu ignoré: %r", kind)
                    ok = True
                if not ok:
                    failed.append(rec)
        except BaseException:
            # Interruption ou erreur inattendue : rendre à la file tout ce qui
            # n'a pas été confirmé, puis laisser remonter.
            sent = len(records) - len(failed)
            self._durable.commit(failed=records[sent:])
            raise
        self._durable.commit(failed=failed)
        if failed:
            self.logger.warning("%s enregistrement(s) toujours en attente", len(failed))

    
    def _send_buffered_heartbeat(self, metrics: dict) -> bool:
        """Envoie un heartbeat bufferisé."""
        headers = {
            "Authorization": self.auth_key
        }
        
        try:
            response = requests.post(
                f"{self.server_url}/api/agents/heartbeat",
                json=metrics,
                headers=headers,
                **self._http_kwargs(),
            )
            
            if response.status_code == 200:
                self.logger.info(f"Heartbeat bufferisé envoyé - CPU: {metrics['cpu_percent']}%, RAM: {metrics['ram_percent']}%")
                return True
            else:
                self.logger.error(f"Erreur heartbeat bufferisé: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            self.logger.error(f"Erreur lors de l'envoi du heartbeat bufferisé: {e}")
            return False

    def _send_buffered_metrics(self, payload: list) -> bool:
        if not payload or not self.auth_key:
            return False
        try:
            response = requests.post(
                f"{self.server_url}/api/ingest/metrics",
                json={"metrics": payload},
                headers={"Authorization": self.auth_key},
                **self._http_kwargs(),
            )
            return response.status_code == 200
        except Exception as e:
            self.logger.error("Buffered metrics send failed: %s", e)
            return False


if __name__ == "__main__":
    # L'analyse des arguments, le verrou d'instance et les verbes
    # d'exploitation vivent dans `cli`. L'ancien code testait
    # `sys.argv[1].endswith('.yaml')` et prenait donc `--config` pour une URL
    # de serveur : aucun agent installé en service ne lisait sa configuration.
    from cli import main as cli_main

    sys.exit(cli_main())
