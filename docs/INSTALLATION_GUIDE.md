# Guide d'Installation - CBC Supervision Platform

Ce guide détaille l'installation complète de la plateforme de supervision CBC, incluant le serveur API, le dashboard web, et l'agent de supervision.

## Table des matières

1. [Prérequis](#prérequis)
2. [Architecture](#architecture)
3. [Installation du Serveur API](#installation-du-serveur-api)
4. [Installation du Dashboard](#installation-du-dashboard)
5. [Installation de l'Agent](#installation-de-lagent)
6. [Configuration de PostgreSQL](#configuration-de-postgresql)
7. [Configuration de Redis](#configuration-de-redis)
8. [Démarrage des services](#démarrage-des-services)
9. [Sécurité SSL/TLS](#sécurité-ssltls)
10. [Maintenance et opérations](#maintenance-et-opérations)

---

## Prérequis

### Système d'exploitation
- Linux (Ubuntu 20.04+ recommandé)
- Windows 10/11 (pour l'agent uniquement)
- macOS (pour l'agent uniquement)

### Logiciels requis

**Pour le serveur API:**
- Python 3.10+
- PostgreSQL 14+
- Redis 6+
- OpenSSL (pour les certificats SSL)

**Pour le dashboard:**
- Node.js 18+
- npm 9+

**Pour l'agent:**
- Python 3.8+
- psutil

---

## Architecture

```
┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
│   Dashboard     │         │   Serveur API   │         │  PostgreSQL     │
│   (React)       │◄────────►   (FastAPI)     │◄────────►  (Base de      │
│   Port 5173     │  HTTPS  │   Port 8443     │  SQL    │   données)      │
└─────────────────┘         └─────────────────┘         └─────────────────┘
                                      │
                                      │
                                      ▼
                              ┌─────────────────┐
                              │   Redis         │
                              │   Port 6379     │
                              └─────────────────┘
                                      ▲
                                      │
                                      │
                              ┌─────────────────┐
                              │   Agents        │
                              │   (Python)      │
                              └─────────────────┘
```

---

## Installation du Serveur API

### 1. Clonage du dépôt

```bash
cd /opt
git clone <repository-url> cbc-supervision
cd cbc-supervision/server
```

### 2. Création de l'environnement virtuel

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Installation des dépendances

```bash
pip install -r requirements.txt
```

### 4. Configuration des variables d'environnement

```bash
cp .env.example .env
```

Éditez le fichier `.env` avec vos valeurs:

```env
# Base de données PostgreSQL
DATABASE_URL=postgresql://cbc_user:cbc_password@localhost:5432/cbc_supervision

# JWT
JWT_SECRET_KEY=votre_secret_key_ici
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# Seuils d'alerte par défaut
CPU_WARNING_THRESHOLD=80
CPU_CRITICAL_THRESHOLD=90
RAM_WARNING_THRESHOLD=80
RAM_CRITICAL_THRESHOLD=90
DISK_WARNING_THRESHOLD=80
DISK_CRITICAL_THRESHOLD=90

# Configuration SMTP (optionnel)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=votre_email@gmail.com
SMTP_PASSWORD=votre_mot_de_passe
SMTP_FROM=noreply@cbc.cm
```

### 5. Initialisation de la base de données

```bash
# Création de la base de données PostgreSQL
sudo -u postgres psql
CREATE DATABASE cbc_supervision;
CREATE USER cbc_user WITH PASSWORD 'cbc_password';
GRANT ALL PRIVILEGES ON DATABASE cbc_supervision TO cbc_user;
\q

# Exécution des migrations Alembic
alembic upgrade head
```

### 6. Génération des certificats SSL

```bash
mkdir ssl
cd ssl
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes
cd ..
```

### 7. Création de l'utilisateur admin par défaut

```bash
python3 -c "from src.database import SessionLocal, engine, Base; from src.models import User; from src.auth_service import get_password_hash; db = SessionLocal(); admin = User(id=str(uuid.uuid4()), username='admin', email='admin@cbc.cm', hashed_password=get_password_hash('admin123'), role='admin'); db.add(admin); db.commit(); print('Admin user created')"
```

---

## Installation du Dashboard

### 1. Accéder au répertoire du dashboard

```bash
cd /opt/cbc-supervision/dashboard
```

### 2. Installation des dépendances

```bash
npm install
```

### 3. Configuration de l'API

Éditez `src/api.js` pour configurer l'URL de l'API:

```javascript
const API_BASE_URL = 'https://localhost:8443/api';
```

### 4. Démarrage en développement

```bash
npm run dev
```

Le dashboard sera accessible sur `http://localhost:5173`

### 5. Build pour la production

```bash
npm run build
```

Les fichiers statiques seront générés dans le répertoire `dist/`.

---

## Installation de l'Agent

### 1. Accéder au répertoire de l'agent

```bash
cd /opt/cbc-supervision/agent
```

### 2. Installation des dépendances

```bash
pip install -r requirements.txt
```

### 3. Configuration de l'agent

```bash
cp config.yaml.example config.yaml
```

Éditez `config.yaml`:

```yaml
server:
  url: "https://localhost:8443"
  enrollment_token: "demo-token-123"

agent:
  heartbeat_interval: 30
  retry_interval: 60
  max_retries: 3

metrics:
  cpu:
    enabled: true
    interval: 1
  memory:
    enabled: true
  disk:
    enabled: true
    path: "/"
  temperature:
    enabled: true
  uptime:
    enabled: true
  latency:
    enabled: true
    target: "8.8.8.8"

degraded_mode:
  enabled: true
  buffer_size: 100
  retry_on_recovery: true

logging:
  level: "INFO"
  file: "agent.log"
  rotation:
    enabled: true
    max_size_mb: 10
    backup_count: 5
```

### 4. Exécution de l'agent

```bash
# Avec fichier de configuration
python3 -m src.agent config.yaml

# Ou avec arguments
python3 -m src.agent https://localhost:8443 demo-token-123
```

### 5. Installation en tant que service (Linux)

Créez le fichier `/etc/systemd/system/cbc-agent.service`:

```ini
[Unit]
Description=CBC Supervision Agent
After=network.target

[Service]
Type=simple
User=cbc
WorkingDirectory=/opt/cbc-supervision/agent
ExecStart=/usr/bin/python3 -m src.agent /opt/cbc-supervision/agent/config.yaml
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Activez et démarrez le service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable cbc-agent
sudo systemctl start cbc-agent
```

---

## Configuration de PostgreSQL

### 1. Installation

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
```

**CentOS/RHEL:**
```bash
sudo yum install postgresql postgresql-server
sudo postgresql-setup initdb
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

### 2. Configuration de la sécurité

Éditez `/etc/postgresql/14/main/pg_hba.conf`:

```conf
# IPv4 local connections:
host    all             all             127.0.0.1/32            scram-sha-256
host    cbc_supervision cbc_user      0.0.0.0/0               scram-sha-256
```

Redémarrez PostgreSQL:

```bash
sudo systemctl restart postgresql
```

### 3. Backup automatique

Le script `scripts/backup_db.sh` est fourni. Configurez une tâche cron:

```bash
# Éditer crontab
crontab -e

# Ajouter une tâche de backup quotidien à 2h du matin
0 2 * * * /opt/cbc-supervision/server/scripts/backup_db.sh
```

---

## Configuration de Redis

### 1. Installation

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install redis-server
```

**CentOS/RHEL:**
```bash
sudo yum install redis
sudo systemctl start redis
sudo systemctl enable redis
```

### 2. Configuration

Éditez `/etc/redis/redis.conf`:

```conf
bind 127.0.0.1
port 6379
maxmemory 256mb
maxmemory-policy allkeys-lru
```

Redémarrez Redis:

```bash
sudo systemctl restart redis
```

---

## Démarrage des services

### Démarrage manuel

**Serveur API:**
```bash
cd /opt/cbc-supervision/server
source venv/bin/activate
python3 -m uvicorn src.main:app --host 0.0.0.0 --port 8443 --ssl-keyfile ssl/key.pem --ssl-certfile ssl/cert.pem
```

**Dashboard:**
```bash
cd /opt/cbc-supervision/dashboard
npm run dev
```

### Démarrage en tant que services (Linux)

**Créez `/etc/systemd/system/cbc-api.service`:**
```ini
[Unit]
Description=CBC Supervision API
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=cbc
WorkingDirectory=/opt/cbc-supervision/server
Environment="PATH=/opt/cbc-supervision/server/venv/bin"
ExecStart=/opt/cbc-supervision/server/venv/bin/uvicorn src.main:app --host 0.0.0.0 --port 8443 --ssl-keyfile ssl/key.pem --ssl-certfile ssl/cert.pem
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Activez et démarrez:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable cbc-api
sudo systemctl start cbc-api
```

---

## Sécurité SSL/TLS

### Certificats auto-signés (développement)

```bash
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes
```

### Certificats Let's Encrypt (production)

```bash
sudo apt install certbot
sudo certbot certonly --standalone -d supervision.cbc.cm
```

Les certificats seront dans `/etc/letsencrypt/live/supervision.cbc.cm/`

Mettez à jour la commande de démarrage:

```bash
--ssl-keyfile /etc/letsencrypt/live/supervision.cbc.cm/privkey.pem \
--ssl-certfile /etc/letsencrypt/live/supervision.cbc.cm/fullchain.pem
```

---

## Maintenance et opérations

### Migrations de base de données

```bash
# Créer une nouvelle migration
alembic revision -m "description_de_la_migration"

# Appliquer les migrations
alembic upgrade head

# Annuler la dernière migration
alembic downgrade -1

# Vérifier l'état des migrations
alembic current
alembic history
```

### Logs

**Serveur API:**
```bash
journalctl -u cbc-api -f
```

**Agent:**
```bash
journalctl -u cbc-agent -f
```

**Dashboard:**
```bash
journalctl -u cbc-dashboard -f
```

### Monitoring

**Health check:**
```bash
curl https://localhost:8443/health
```

**Métriques Prometheus:**
```bash
curl https://localhost:8443/metrics
```

### Mise à jour

**Serveur API:**
```bash
cd /opt/cbc-supervision/server
git pull
source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
sudo systemctl restart cbc-api
```

**Dashboard:**
```bash
cd /opt/cbc-supervision/dashboard
git pull
npm install
npm run build
sudo systemctl restart cbc-dashboard
```

**Agent:**
```bash
cd /opt/cbc-supervision/agent
git pull
pip install -r requirements.txt
sudo systemctl restart cbc-agent
```

---

## Dépannage

### L'agent ne se connecte pas

1. Vérifiez que le serveur API est en cours d'exécution
2. Vérifiez les logs de l'agent: `journalctl -u cbc-agent -n 50`
3. Vérifiez la configuration réseau et les certificats SSL
4. Testez la connexion: `curl -k https://localhost:8443/health`

### Le dashboard ne charge pas les données

1. Vérifiez que le serveur API est accessible
2. Vérifiez les logs du navigateur (F12)
3. Vérifiez que le token JWT est valide
4. Testez l'API: `curl https://localhost:8443/api/agents`

### Erreur de connexion PostgreSQL

1. Vérifiez que PostgreSQL est en cours d'exécution: `sudo systemctl status postgresql`
2. Vérifiez les identifiants dans `.env`
3. Vérifiez que la base de données existe: `sudo -u postgres psql -l`

### Erreur de connexion Redis

1. Vérifiez que Redis est en cours d'exécution: `sudo systemctl status redis`
2. Vérifiez la configuration: `redis-cli ping`

---

## Support

Pour toute question ou problème, contactez l'équipe technique à `support@cbc.cm`.
