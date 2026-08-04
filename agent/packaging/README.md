# CBC Supervision Agent - Guide de Packaging

Ce guide explique comment construire et installer l'agent CBC Supervision sur différentes plateformes.

## Prérequis

### Communs à toutes les plateformes
- Python 3.8 ou supérieur
- pip (gestionnaire de paquets Python)

### Dépendances Python
```bash
pip install pyinstaller psutil requests pyyaml
```

### Spécifiques par plateforme

#### Linux (Debian/Ubuntu)
```bash
sudo apt-get install python3 python3-pip python3-psutil python3-requests python3-yaml
# Pour le packaging DEB
sudo apt-get install dpkg-dev
# Pour le packaging RPM
sudo apt-get install rpmbuild
```

#### Linux (RedHat/CentOS)
```bash
sudo yum install python3 python3-pip
sudo pip3 install psutil requests pyyaml
# Pour le packaging RPM
sudo yum install rpm-build
```

#### macOS
```bash
# Installer Homebrew si nécessaire
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew install python3
# Pour le packaging PKG
# Xcode Command Line Tools requis
xcode-select --install
```

#### Windows
- Python 3.8+ depuis https://python.org
- Pour le packaging MSI: WiX Toolset depuis https://wixtoolset.org/

## Construction des Packages

### Construction sur Linux

```bash
cd agent/packaging
chmod +x build_linux.sh
./build_linux.sh
```

Cela créera :
- `dist/cbc-agent_1.0.0_amd64.deb` (Package Debian/Ubuntu)
- `dist/cbc-agent-1.0.0-1.x86_64.rpm` (Package RedHat/CentOS, si rpmbuild est installé)

### Construction sur macOS

```bash
cd agent/packaging
chmod +x build_macos.sh
./build_macos.sh
```

Cela créera :
- `dist/cbc-agent-1.0.0.pkg` (Package macOS)

### Construction sur Windows

```powershell
cd agent\packaging
.\build_windows.ps1
```

Cela créera :
- `dist/cbc-agent-1.0.0.msi` (Package Windows, si WiX est installé)

### Construction avec le script Python

```bash
cd agent
python packaging/build.py all
```

Commandes disponibles :
- `python packaging/build.py clean` - Nettoyer les répertoires de build
- `python packaging/build.py exe` - Construire uniquement l'exécutable
- `python packaging/build.py deb` - Construire le package DEB
- `python packaging/build.py rpm` - Construire le package RPM
- `python packaging/build.py pkg` - Construire le package PKG
- `python packaging/build.py msi` - Construire le package MSI
- `python packaging/build.py all` - Construire tous les packages pour la plateforme actuelle

## Installation

### Installation automatique

#### Linux (Debian/Ubuntu)
```bash
sudo dpkg -i cbc-agent_1.0.0_amd64.deb
sudo apt-get install -f  # Pour résoudre les dépendances
```

#### Linux (RedHat/CentOS)
```bash
sudo rpm -i cbc-agent-1.0.0-1.x86_64.rpm
```

#### macOS
```bash
sudo installer -pkg cbc-agent-1.0.0.pkg -target /
```

#### Windows
```powershell
msiexec /i cbc-agent-1.0.0.msi /quiet /norestart
```

### Installation avec le script universel

```bash
cd agent/packaging
chmod +x install.sh
./install.sh
```

Ce script détecte automatiquement la plateforme et installe l'agent avec les dépendances appropriées.

### Installation manuelle

#### Linux/macOS
```bash
# Installer les dépendances
pip3 install psutil requests pyyaml

# Copier l'exécutable
sudo cp cbc-agent /usr/local/bin/
sudo chmod +x /usr/local/bin/cbc-agent

# Créer le répertoire de configuration
sudo mkdir -p /etc/cbc-agent

# Créer le fichier de configuration
sudo nano /etc/cbc-agent/config.yaml
```

#### Windows
```powershell
# Installer les dépendances
pip install psutil requests pyyaml

# Créer le répertoire d'installation
mkdir "C:\Program Files\CBC Agent"

# Copier l'exécutable
copy cbc-agent.exe "C:\Program Files\CBC Agent\"

# Créer le répertoire de configuration
mkdir "C:\ProgramData\CBC Agent"

# Créer le fichier de configuration
notepad "C:\ProgramData\CBC Agent\config.yaml"
```

## Configuration

Le fichier de configuration se trouve à :

- **Linux/macOS**: `/etc/cbc-agent/config.yaml`
- **Windows**: `C:\Program Files\CBC Agent\config.yaml` ou `C:\ProgramData\CBC Agent\config.yaml`

Exemple de configuration :
```yaml
server:
  url: https://localhost:8443
  enrollment_token: your-token-here

agent:
  heartbeat_interval: 30
  retry_interval: 60
  max_retries: 3

metrics:
  cpu: true
  memory: true
  disk: true
  network: true

degraded_mode:
  enabled: true
  buffer_size: 100

logging:
  level: INFO
  file: /var/log/cbc-agent/agent.log
  max_size: 10485760
  backup_count: 5
```

## Gestion du Service

### Linux (systemd)
```bash
# Démarrer le service
sudo systemctl start cbc-agent

# Arrêter le service
sudo systemctl stop cbc-agent

# Redémarrer le service
sudo systemctl restart cbc-agent

# Vérifier le statut
sudo systemctl status cbc-agent

# Activer au démarrage
sudo systemctl enable cbc-agent

# Voir les logs
sudo journalctl -u cbc-agent -f
```

### macOS (launchd)
```bash
# Démarrer le service
sudo launchctl start com.cbc.agent

# Arrêter le service
sudo launchctl stop com.cbc.agent

# Vérifier le statut
sudo launchctl list | grep cbc-agent

# Voir les logs
tail -f /var/log/cbc-agent/agent.log
```

### Windows (Service Windows)
```powershell
# Démarrer le service
Start-Service -Name "CBCAgent"

# Arrêter le service
Stop-Service -Name "CBCAgent"

# Redémarrer le service
Restart-Service -Name "CBCAgent"

# Vérifier le statut
Get-Service -Name "CBCAgent"

# Voir les logs
Get-Content "C:\ProgramData\CBC Agent\agent.log" -Wait
```

## Dépannage

### L'agent ne démarre pas

1. Vérifier les logs :
   - Linux: `sudo journalctl -u cbc-agent`
   - macOS: `tail -f /var/log/cbc-agent/agent.log`
   - Windows: `Get-Content "C:\ProgramData\CBC Agent\agent.log"`

2. Vérifier la configuration :
   ```bash
   cbc-agent --config /etc/cbc-agent/config.yaml --validate
   ```

3. Vérifier la connexion au serveur :
   ```bash
   curl -k https://localhost:8443/api/health
   ```

### Erreur de connexion SSL

Si vous utilisez un certificat auto-signé en développement, vous pouvez désactiver la vérification SSL dans la configuration :

```yaml
server:
  url: https://localhost:8443
  verify_ssl: false
```

### Permissions insuffisantes

Assurez-vous que l'agent a les permissions nécessaires pour :
- Lire les métriques système
- Écrire dans les fichiers de log
- Se connecter au serveur

## Mise à jour

### Linux (Debian/Ubuntu)
```bash
sudo dpkg -i cbc-agent_1.0.1_amd64.deb
```

### Linux (RedHat/CentOS)
```bash
sudo rpm -U cbc-agent-1.0.1-1.x86_64.rpm
```

### macOS
```bash
sudo installer -pkg cbc-agent-1.0.1.pkg -target /
```

### Windows
```powershell
msiexec /i cbc-agent-1.0.1.msi /quiet /norestart
```

## Désinstallation

### Linux (Debian/Ubuntu)
```bash
sudo apt-get remove cbc-agent
```

### Linux (RedHat/CentOS)
```bash
sudo rpm -e cbc-agent
```

### macOS
```bash
sudo launchctl stop com.cbc.agent
sudo launchctl unload /Library/LaunchDaemons/com.cbc.agent.plist
sudo rm -rf /usr/local/bin/cbc-agent
sudo rm -rf /etc/cbc-agent
sudo rm /Library/LaunchDaemons/com.cbc.agent.plist
```

### Windows
```powershell
msiexec /x cbc-agent-1.0.0.msi /quiet
```

## Support

Pour toute question ou problème, contactez :
- Email: support@cbcam.cm
- Documentation: https://github.com/cbc/cbc-supervision
- Issues: https://github.com/cbc/cbc-supervision/issues
