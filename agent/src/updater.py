#!/usr/bin/env python3
"""
Module de mise à jour automatique pour l'agent CBC Supervision
Permet les mises à jour à distance depuis un serveur central
"""

import os
import sys
import json
import hashlib
import requests
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import Optional, Dict, Tuple
import logging

# Configuration
UPDATE_SERVER_URL = os.getenv("UPDATE_SERVER_URL", "https://download.cbc-cam.cm/cbc-agent")
CURRENT_VERSION = "1.0.0"
UPDATE_CHECK_INTERVAL = 3600  # 1 heure en secondes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class UpdateManager:
    """Gestionnaire de mises à jour automatiques"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.update_server = config.get("update_server", UPDATE_SERVER_URL)
        self.current_version = CURRENT_VERSION
        self.auto_update = config.get("auto_update", True)
        self.update_interval = config.get("update_interval", UPDATE_CHECK_INTERVAL)
        
    def check_for_updates(self) -> Optional[Dict]:
        """Vérifie si une mise à jour est disponible"""
        try:
            logger.info("Vérification des mises à jour...")
            
            # Récupérer les informations de version
            version_url = f"{self.update_server}/version.json"
            response = requests.get(version_url, timeout=10)
            response.raise_for_status()
            
            version_info = response.json()
            latest_version = version_info.get("version")
            
            if not latest_version:
                logger.warning("Impossible de récupérer la version")
                return None
            
            logger.info(f"Version actuelle: {self.current_version}, Version disponible: {latest_version}")
            
            # Comparer les versions
            if self._compare_versions(latest_version, self.current_version) > 0:
                logger.info(f"Nouvelle version disponible: {latest_version}")
                return {
                    "current_version": self.current_version,
                    "latest_version": latest_version,
                    "download_url": version_info.get("download_url"),
                    "checksum": version_info.get("checksum"),
                    "release_notes": version_info.get("release_notes", "")
                }
            
            logger.info("L'agent est à jour")
            return None
            
        except requests.RequestException as e:
            logger.error(f"Erreur lors de la vérification des mises à jour: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Erreur lors du parsing des informations de version: {e}")
            return None
    
    def download_update(self, update_info: Dict) -> Optional[Path]:
        """Télécharge la mise à jour"""
        try:
            logger.info(f"Téléchargement de la version {update_info['latest_version']}...")
            
            download_url = update_info["download_url"]
            response = requests.get(download_url, stream=True, timeout=30)
            response.raise_for_status()
            
            # Créer un fichier temporaire
            temp_dir = Path(tempfile.mkdtemp(prefix="cbc-agent-update-"))
            package_file = temp_dir / f"cbc-agent-{update_info['latest_version']}.pkg"
            
            # Télécharger le fichier
            with open(package_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # Vérifier le checksum si fourni
            if update_info.get("checksum"):
                if not self._verify_checksum(package_file, update_info["checksum"]"):
                    logger.error("Checksum invalide")
                    shutil.rmtree(temp_dir)
                    return None
            
            logger.info(f"Téléchargement terminé: {package_file}")
            return package_file
            
        except requests.RequestException as e:
            logger.error(f"Erreur lors du téléchargement: {e}")
            return None
        except Exception as e:
            logger.error(f"Erreur inattendue: {e}")
            return None
    
    def install_update(self, package_file: Path) -> bool:
        """Installe la mise à jour"""
        try:
            logger.info("Installation de la mise à jour...")
            
            # Déterminer la plateforme
            platform = sys.platform
            
            if platform == "linux":
                return self._install_linux_update(package_file)
            elif platform == "darwin":
                return self._install_macos_update(package_file)
            elif platform == "win32":
                return self._install_windows_update(package_file)
            else:
                logger.error(f"Plateforme non supportée: {platform}")
                return False
                
        except Exception as e:
            logger.error(f"Erreur lors de l'installation: {e}")
            return False
    
    def _install_linux_update(self, package_file: Path) -> bool:
        """Installe la mise à jour sur Linux"""
        try:
            # Détecter le type de package
            if package_file.suffix == ".deb":
                cmd = ["sudo", "dpkg", "-i", str(package_file)]
                subprocess.run(cmd, check=True)
            elif package_file.suffix == ".rpm":
                cmd = ["sudo", "rpm", "-U", str(package_file)]
                subprocess.run(cmd, check=True)
            else:
                logger.error("Type de package non supporté")
                return False
            
            logger.info("Mise à jour installée avec succès")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Erreur lors de l'installation: {e}")
            return False
    
    def _install_macos_update(self, package_file: Path) -> bool:
        """Installe la mise à jour sur macOS"""
        try:
            cmd = ["sudo", "installer", "-pkg", str(package_file), "-target", "/"]
            subprocess.run(cmd, check=True)
            logger.info("Mise à jour installée avec succès")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Erreur lors de l'installation: {e}")
            return False
    
    def _install_windows_update(self, package_file: Path) -> bool:
        """Installe la mise à jour sur Windows"""
        try:
            if package_file.suffix == ".msi":
                cmd = ["msiexec", "/i", str(package_file), "/quiet", "/norestart"]
                subprocess.run(cmd, check=True)
            else:
                logger.error("Type de package non supporté")
                return False
            
            logger.info("Mise à jour installée avec succès")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Erreur lors de l'installation: {e}")
            return False
    
    def _compare_versions(self, version1: str, version2: str) -> int:
        """Compare deux versions (retourne 1 si v1 > v2, -1 si v1 < v2, 0 si égal)"""
        v1_parts = [int(x) for x in version1.split(".")]
        v2_parts = [int(x) for x in version2.split(".")]
        
        for i in range(max(len(v1_parts), len(v2_parts))):
            v1 = v1_parts[i] if i < len(v1_parts) else 0
            v2 = v2_parts[i] if i < len(v2_parts) else 0
            
            if v1 > v2:
                return 1
            elif v1 < v2:
                return -1
        
        return 0
    
    def _verify_checksum(self, file_path: Path, expected_checksum: str) -> bool:
        """Vérifie le checksum du fichier"""
        try:
            sha256_hash = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(chunk)
            
            actual_checksum = sha256_hash.hexdigest()
            return actual_checksum == expected_checksum
            
        except Exception as e:
            logger.error(f"Erreur lors de la vérification du checksum: {e}")
            return False
    
    def perform_update(self) -> bool:
        """Effectue le processus complet de mise à jour"""
        if not self.auto_update:
            logger.info("Mise à jour automatique désactivée")
            return False
        
        # Vérifier les mises à jour
        update_info = self.check_for_updates()
        if not update_info:
            return False
        
        # Télécharger la mise à jour
        package_file = self.download_update(update_info)
        if not package_file:
            return False
        
        # Installer la mise à jour
        success = self.install_update(package_file)
        
        # Nettoyer
        if package_file.parent.exists():
            shutil.rmtree(package_file.parent)
        
        if success:
            logger.info("Mise à jour terminée avec succès. Redémarrage de l'agent...")
            # Redémarrer l'agent
            self._restart_agent()
        
        return success
    
    def _restart_agent(self) -> None:
        """Redémarre l'agent après la mise à jour"""
        try:
            platform = sys.platform
            
            if platform == "linux":
                subprocess.run(["sudo", "systemctl", "restart", "cbc-agent"])
            elif platform == "darwin":
                subprocess.run(["sudo", "launchctl", "restart", "com.cbc.agent"])
            elif platform == "win32":
                subprocess.run(["sc", "start", "CBCAgent"])
                
        except Exception as e:
            logger.error(f"Erreur lors du redémarrage: {e}")


def main():
    """Point d'entrée principal pour les tests"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Gestionnaire de mises à jour CBC Agent")
    parser.add_argument("--check", action="store_true", help="Vérifier les mises à jour")
    parser.add_argument("--update", action="store_true", help="Effectuer la mise à jour")
    parser.add_argument("--config", help="Fichier de configuration")
    
    args = parser.parse_args()
    
    # Charger la configuration
    config = {}
    if args.config:
        with open(args.config, 'r') as f:
            import yaml
            config = yaml.safe_load(f)
    
    updater = UpdateManager(config)
    
    if args.check:
        update_info = updater.check_for_updates()
        if update_info:
            print(f"Nouvelle version disponible: {update_info['latest_version']}")
            print(f"Notes de version: {update_info.get('release_notes', '')}")
        else:
            print("L'agent est à jour")
    
    if args.update:
        updater.perform_update()


if __name__ == "__main__":
    main()
