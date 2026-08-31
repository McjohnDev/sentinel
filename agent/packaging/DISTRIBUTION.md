# Guide de Distribution et Mise à Jour de l'Agent CBC Supervision

Ce guide explique comment distribuer l'agent CBC Supervision et configurer les mises à jour automatiques.

## Architecture de Distribution

### Composants

1. **Serveur de Distribution** - Héberge les packages d'installation
2. **Script d'Installation** - Script universel pour l'installation
3. **Système de Mise à Jour** - Module intégré pour les mises à jour automatiques
4. **Fichier de Version** - Informations sur les versions disponibles

## Installation silencieuse (FS2-06)

Aucune interaction n’est requise pour le déploiement de masse :

```bash
# Debian / Ubuntu
sudo DEBIAN_FRONTEND=noninteractive dpkg -i cbc-agent_1.0.0_amd64.deb

# RHEL / Rocky
sudo rpm -Uvh --quiet cbc-agent-1.0.0-1.x86_64.rpm

# macOS
sudo installer -pkg cbc-agent-1.0.0.pkg -target / -quiet

# Windows (cmd / GPO / Intune)
msiexec /i cbc-agent-1.0.0.msi /qn /norestart
```

Puis déposer `config.yaml` (URL serveur + jeton d’enrôlement) dans le répertoire de l’agent.

## Configuration du Serveur de Distribution

### Structure du Serveur

```
download.cbc-cam.cm/
└── cbc-agent/
    ├── version.json              # Informations de version
    ├── cbc-agent_1.0.0_amd64.deb # Package Debian/Ubuntu
    ├── cbc-agent-1.0.0-1.x86_64.rpm # Package RedHat/CentOS
    ├── cbc-agent-1.0.0.pkg       # Package macOS
    ├── cbc-agent-1.0.0.msi       # Package Windows
    └── install.sh                # Script d'installation
```

### Configuration du Serveur Web

Vous pouvez utiliser n'importe quel serveur web (Apache, Nginx, AWS S3, etc.).

**Exemple Nginx :**

```nginx
server {
    listen 80;
    server_name download.cbc-cam.cm;
    
    root /var/www/download;
    
    location /cbc-agent/ {
        autoindex on;
        add_header Content-Type application/octet-stream;
    }
}
```

**Exemple AWS S3 :**

```bash
# Créer le bucket
aws s3 mb s3://cbc-agent-downloads

# Configurer comme site web statique
aws s3 website s3://cbc-agent-downloads --index-document version.json

# Uploader les fichiers
aws s3 sync ./dist/ s3://cbc-agent-downloads/cbc-agent/
```

## Méthodes d'Installation

### Méthode 1: Script d'Installation en Ligne

Les utilisateurs peuvent installer l'agent avec une seule commande :

```bash
curl -fsSL https://download.cbc-cam.cm/cbc-agent/install.sh | bash
```

Ou :

```bash
wget -qO- https://download.cbc-cam.cm/cbc-agent/install.sh | bash
```

### Méthode 2: Téléchargement Manuel

Les utilisateurs peuvent télécharger et exécuter le script :

```bash
wget https://download.cbc-cam.cm/cbc-agent/install.sh
chmod +x install.sh
./install.sh
```

### Méthode 3: Dépôts de Paquets (APT/YUM)

Pour une distribution plus professionnelle, vous pouvez créer des dépôts APT/YUM.

**Dépôt APT (Debian/Ubuntu) :**

```bash
# Installer les outils nécessaires
sudo apt-get install reprepro

# Créer la structure du dépôt
mkdir -p /var/www/repo/conf
cd /var/www/repo

# Créer le fichier de configuration
cat > conf/distributions << EOF
Origin: CBC Supervision
Label: CBC Agent
Suite: stable
Codename: jammy
Architectures: amd64
Components: main
Description: Dépôt pour l'agent CBC Supervision
SignWith: YOUR_GPG_KEY_ID
EOF

# Ajouter le package
reprepro includedeb stable cbc-agent_1.0.0_amd64.deb
```

**Configuration client :**

```bash
# Ajouter la clé GPG
wget -qO - https://download.cbc-cam.cm/repo/gpg.key | sudo apt-key add -

# Ajouter le dépôt
echo "deb https://download.cbc-cam.cm/repo stable main" | sudo tee /etc/apt/sources.list.d/cbc-agent.list

# Installer
sudo apt-get update
sudo apt-get install cbc-agent
```

## Configuration des Mises à Jour Automatiques

### Activation dans la Configuration

Ajoutez ces paramètres au fichier de configuration `/etc/cbc-agent/config.yaml` :

```yaml
update:
  enabled: true
  server_url: https://download.cbc-cam.cm/cbc-agent
  check_interval: 3600  # Vérifier toutes les heures
  auto_install: true   # Installer automatiquement les mises à jour
  notify_before_update: true
```

### Intégration dans l'Agent

Ajoutez le module de mise à jour dans votre agent principal :

```python
from updater import UpdateManager

# Dans votre agent principal
def check_updates():
    config = load_config()
    updater = UpdateManager(config)
    updater.perform_update()

# Exécuter périodiquement
import threading
update_thread = threading.Timer(config['update']['check_interval'], check_updates)
update_thread.start()
```

## Processus de Publication d'une Nouvelle Version

### 1. Construire les Packages

```bash
cd agent
python3 packaging/build.py all
```

### 2. Générer les Checksums

```bash
cd agent/packaging/dist
sha256sum *.deb *.rpm *.pkg *.msi > checksums.txt
```

### 3. Mettre à Jour version.json

```json
{
  "version": "1.0.1",
  "release_date": "2026-08-05",
  "download_url": "https://download.cbc-cam.cm/cbc-agent/cbc-agent-1.0.1.tar.gz",
  "checksum": "sha256:ACTUAL_CHECKSUM_HERE",
  "release_notes": "Nouvelles fonctionnalités et corrections de bugs",
  "platforms": {
    "linux": {
      "deb": "https://download.cbc-cam.cm/cbc-agent/cbc-agent_1.0.1_amd64.deb",
      "rpm": "https://download.cbc-cam.cm/cbc-agent/cbc-agent-1.0.1-1.x86_64.rpm"
    }
  }
}
```

### 4. Uploader vers le Serveur

```bash
# Pour AWS S3
aws s3 sync ./dist/ s3://cbc-agent-downloads/cbc-agent/

# Pour un serveur web
scp -r ./dist/* user@download.cbc-cam.cm:/var/www/download/cbc-agent/
```

### 5. Notifier les Utilisateurs

Les agents vérifieront automatiquement les mises à jour selon l'intervalle configuré.

## Sécurité

### Signatures GPG

Signez vos packages pour garantir leur authenticité :

```bash
# Signer un package DEB
dpkg-sig --sign builder cbc-agent_1.0.0_amd64.deb

# Signer un package RPM
rpmsign --addsign cbc-agent-1.0.0-1.x86_64.rpm
```

### HTTPS

Assurez-vous que votre serveur de distribution utilise HTTPS :

```bash
# Certbot pour Let's Encrypt
sudo certbot --nginx -d download.cbc-cam.cm
```

### Vérification des Checksums

Le système de mise à jour vérifie automatiquement les checksums SHA256 avant l'installation.

## Monitoring

### Statistiques de Téléchargement

Utilisez Google Analytics ou un outil similaire pour suivre les téléchargements :

```html
<!-- Dans votre page de téléchargement -->
<script async src="https://www.googletagmanager.com/gtag/js?id=GA_TRACKING_ID"></script>
```

### Statistiques d'Installation

L'agent peut envoyer des statistiques anonymes lors de l'installation :

```python
def report_installation():
    stats = {
        "version": CURRENT_VERSION,
        "platform": sys.platform,
        "architecture": platform.machine(),
        "install_date": datetime.now().isoformat()
    }
    requests.post("https://api.cbc-cam.cm/install-stats", json=stats)
```

## Dépannage

### Problème: L'agent ne détecte pas les mises à jour

**Solution :**
- Vérifiez que `update.enabled` est `true` dans la configuration
- Vérifiez la connectivité au serveur de mise à jour
- Consultez les logs : `/var/log/cbc-agent/agent.log`

### Problème: Échec du téléchargement

**Solution :**
- Vérifiez que l'URL de téléchargement est correcte
- Vérifiez que le serveur est accessible
- Vérifiez les permissions réseau

### Problème: Échec de l'installation

**Solution :**
- Vérifiez les permissions (sudo requis)
- Vérifiez l'espace disque disponible
- Consultez les logs du système de paquets

## Bonnes Pratiques

1. **Testez toujours** les mises à jour sur un environnement de test
2. **Communiquez** les mises à jour majeures à l'avance
3. **Maintenez** la compatibilité descendante quand possible
4. **Documentez** les changements de configuration
5. **Sauvegardez** les configurations avant les mises à jour
6. **Surveillez** les taux de succès des mises à jour

## Support

Pour toute question sur la distribution et les mises à jour :
- Email: support@cbcam.cm
- Documentation: https://github.com/cbc/cbc-supervision
- Issues: https://github.com/cbc/cbc-supervision/issues
