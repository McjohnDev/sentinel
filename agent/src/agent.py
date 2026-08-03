import psutil
import socket
import platform
import uuid
import time
import requests
from datetime import datetime
import json
import yaml
import os
import logging
from logging.handlers import RotatingFileHandler
from typing import Dict, Any


class CBCAgent:
    """Agent de supervision CBC."""
    
    def __init__(self, config_path: str = None, server_url: str = None, enrollment_token: str = None):
        self.config = self._load_config(config_path) if config_path else {}
        
        # Priorité: config YAML > arguments > valeurs par défaut
        self.server_url = self.config.get('server', {}).get('url', server_url or "https://localhost:8443")
        self.enrollment_token = self.config.get('server', {}).get('enrollment_token', enrollment_token or "demo-token-123")
        
        self.agent_id = None
        self.auth_key = None
        self.machine_id = self._get_or_generate_machine_id()
        
        agent_config = self.config.get('agent', {})
        self.heartbeat_interval = agent_config.get('heartbeat_interval', 30)
        self.retry_interval = agent_config.get('retry_interval', 60)
        self.max_retries = agent_config.get('max_retries', 3)
        
        self.metrics_config = self.config.get('metrics', {})
        self.degraded_mode_config = self.config.get('degraded_mode', {})
        self.logging_config = self.config.get('logging', {})
        
        self.heartbeat_buffer = []  # Buffer pour le mode dégradé
        self.retries = 0
        
        # Configuration du logging
        self._setup_logging()
    
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
        """Génère ou récupère le Machine ID."""
        # Pour le MVP, on génère un UUID persistant
        # En production, utiliser /etc/machine-id sur Linux, registry sur Windows, etc.
        return str(uuid.uuid4())
    
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
        return "1.0.0"
    
    def collect_metrics(self) -> dict:
        """Collecte toutes les métriques système."""
        # CPU
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_cores = psutil.cpu_count(logical=True)
        cpu_architecture = platform.machine()
        
        # RAM
        ram = psutil.virtual_memory()
        ram_percent = ram.percent
        ram_total_gb = ram.total / (1024**3)
        ram_used_gb = ram.used / (1024**3)
        ram_free_gb = ram.available / (1024**3)
        
        # Disque
        disk = psutil.disk_usage('/')
        disk_percent = disk.percent
        disk_total_gb = disk.total / (1024**3)
        disk_used_gb = disk.used / (1024**3)
        disk_free_gb = disk.free / (1024**3)
        
        # Uptime
        uptime_seconds = int(time.time() - psutil.boot_time())
        
        # Latence (ping simplifié)
        latency_ms = self._measure_latency()
        
        # Température CPU (optionnel)
        temperature_celsius = self._get_cpu_temperature()
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "cpu_percent": cpu_percent,
            "cpu_cores": cpu_cores,
            "cpu_architecture": cpu_architecture,
            "ram_percent": ram_percent,
            "ram_total_gb": round(ram_total_gb, 2),
            "ram_used_gb": round(ram_used_gb, 2),
            "ram_free_gb": round(ram_free_gb, 2),
            "disk_percent": disk_percent,
            "disk_total_gb": round(disk_total_gb, 2),
            "disk_used_gb": round(disk_used_gb, 2),
            "disk_free_gb": round(disk_free_gb, 2),
            "uptime_seconds": uptime_seconds,
            "latency_ms": latency_ms,
            "temperature_celsius": temperature_celsius
        }
    
    def _measure_latency(self) -> float:
        """Mesure la latence vers le serveur."""
        try:
            start = time.time()
            requests.get(f"{self.server_url}/", timeout=5, verify=False)
            return round((time.time() - start) * 1000, 2)
        except:
            return None
    
    def _get_cpu_temperature(self) -> float:
        """Récupère la température CPU si disponible."""
        try:
            temps = psutil.sensors_temperatures()
            if temps:
                for name, entries in temps.items():
                    if entries:
                        return entries[0].current
        except:
            pass
        return None
    
    def enroll(self) -> bool:
        """Enrôle l'agent auprès du serveur."""
        hostname = self._get_hostname()
        os_name, os_version = self._get_os_info()
        agent_version = self._get_agent_version()
        
        payload = {
            "token": self.enrollment_token,
            "machine_id": self.machine_id,
            "hostname": hostname,
            "os": os_name,
            "os_version": os_version,
            "agent_version": agent_version
        }
        
        try:
            response = requests.post(
                f"{self.server_url}/api/agents/enroll",
                json=payload,
                timeout=10,
                verify=False
            )
            
            if response.status_code == 200:
                data = response.json()
                self.agent_id = data["agent_id"]
                self.auth_key = data["auth_key"]
                self.logger.info(f"Agent enregistré avec succès. ID: {self.agent_id}")
                return True
            else:
                self.logger.error(f"Erreur d'enrôlement: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            self.logger.error(f"Erreur lors de l'enrôlement: {e}")
            return False
    
    def send_heartbeat(self) -> bool:
        """Envoie un heartbeat au serveur."""
        if not self.auth_key:
            self.logger.error("Agent non enregistré")
            return False
        
        metrics = self.collect_metrics()
        
        headers = {
            "Authorization": self.auth_key
        }
        
        try:
            response = requests.post(
                f"{self.server_url}/api/agents/heartbeat",
                json=metrics,
                headers=headers,
                timeout=10,
                verify=False
            )
            
            if response.status_code == 200:
                self.logger.info(f"Heartbeat envoyé - CPU: {metrics['cpu_percent']}%, RAM: {metrics['ram_percent']}%")
                return True
            else:
                self.logger.error(f"Erreur heartbeat: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            self.logger.error(f"Erreur lors de l'envoi du heartbeat: {e}")
            return False
    
    def run(self):
        """Boucle principale de l'agent."""
        self.logger.info(f"Démarrage de l'agent CBC Supervision...")
        self.logger.info(f"Serveur: {self.server_url}")
        self.logger.info(f"Machine ID: {self.machine_id}")
        self.logger.info(f"Intervalle heartbeat: {self.heartbeat_interval}s")
        
        # Enrôlement
        if not self.enroll():
            self.logger.error("Échec de l'enrôlement. Arrêt de l'agent.")
            return
        
        # Boucle de heartbeat avec mode dégradé
        self.logger.info(f"Démarrage des heartbeats (intervalle: {self.heartbeat_interval}s)...")
        self.logger.info(f"Mode dégradé: {'activé' if self.degraded_mode_config.get('enabled', True) else 'désactivé'}")
        
        while True:
            if self.send_heartbeat():
                self.retries = 0
                # Envoyer les heartbeats bufferisés si connexion rétablie
                if self.degraded_mode_config.get('retry_on_recovery', True) and self.heartbeat_buffer:
                    self.logger.info(f"Envoi de {len(self.heartbeat_buffer)} heartbeats bufferisés...")
                    for buffered_heartbeat in self.heartbeat_buffer:
                        self._send_buffered_heartbeat(buffered_heartbeat)
                    self.heartbeat_buffer.clear()
            else:
                self.retries += 1
                self.logger.warning(f"Échec heartbeat (tentative {self.retries}/{self.max_retries})")
                
                # Mode dégradé: stocker localement
                if self.degraded_mode_config.get('enabled', True):
                    metrics = self.collect_metrics()
                    buffer_size = self.degraded_mode_config.get('buffer_size', 100)
                    self.heartbeat_buffer.append(metrics)
                    
                    if len(self.heartbeat_buffer) > buffer_size:
                        self.heartbeat_buffer.pop(0)  # Supprimer le plus ancien
                    
                    self.logger.info(f"Heartbeat stocké en local (buffer: {len(self.heartbeat_buffer)}/{buffer_size})")
                
                if self.retries >= self.max_retries:
                    self.logger.warning(f"Nombre maximum de tentatives atteint. Attente de {self.retry_interval}s avant réessai...")
                    time.sleep(self.retry_interval)
                    self.retries = 0
            
            time.sleep(self.heartbeat_interval)
    
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
                timeout=10,
                verify=False
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


if __name__ == "__main__":
    import sys
    
    # Configuration par défaut
    CONFIG_PATH = None
    SERVER_URL = None
    ENROLLMENT_TOKEN = None
    
    # Permettre de passer le fichier de config, l'URL et le token en arguments
    if len(sys.argv) > 1 and sys.argv[1].endswith('.yaml'):
        CONFIG_PATH = sys.argv[1]
    elif len(sys.argv) > 1:
        SERVER_URL = sys.argv[1]
    
    if len(sys.argv) > 2:
        ENROLLMENT_TOKEN = sys.argv[2]
    
    agent = CBCAgent(config_path=CONFIG_PATH, server_url=SERVER_URL, enrollment_token=ENROLLMENT_TOKEN)
    agent.run()
