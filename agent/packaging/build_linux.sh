#!/bin/bash
# Script de build pour Linux (DEB/RPM)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "🔨 Construction de l'agent pour Linux..."

# Nettoyage
echo "🧹 Nettoyage..."
rm -rf "$PROJECT_ROOT/packaging/build"
rm -rf "$PROJECT_ROOT/packaging/dist"
mkdir -p "$PROJECT_ROOT/packaging/build"
mkdir -p "$PROJECT_ROOT/packaging/dist"

# Construction de l'exécutable
echo "📦 Construction de l'exécutable avec PyInstaller..."
cd "$PROJECT_ROOT"
pyinstaller --clean --noconfirm packaging/agent.spec

# Construction du package DEB
echo "🔨 Construction du package DEB..."
BUILD_DIR="$PROJECT_ROOT/packaging/build/deb"
mkdir -p "$BUILD_DIR/DEBIAN"
mkdir -p "$BUILD_DIR/usr/bin"
mkdir -p "$BUILD_DIR/etc/cbc-agent"
mkdir -p "$BUILD_DIR/etc/systemd/system"

# Copie de l'exécutable
if [ -f "$PROJECT_ROOT/dist/cbc-agent" ]; then
    cp "$PROJECT_ROOT/dist/cbc-agent" "$BUILD_DIR/usr/bin/cbc-agent"
    chmod +x "$BUILD_DIR/usr/bin/cbc-agent"
fi

# Création du fichier de contrôle
cat > "$BUILD_DIR/DEBIAN/control" << EOF
Package: cbc-agent
Version: 1.0.0
Section: utils
Priority: optional
Architecture: amd64
Maintainer: CBC Supervision <support@cbcam.cm>
Description: CBC Supervision Agent
 Agent de supervision pour le système CBC Supervision Platform.
 Collecte les métriques système et les envoie au serveur central.
Depends: python3, python3-psutil, python3-requests, python3-yaml
EOF

# Création du script post-install
cat > "$BUILD_DIR/DEBIAN/postinst" << 'EOF'
#!/bin/bash
set -e

# Créer le répertoire de configuration
mkdir -p /etc/cbc-agent

# Créer le fichier de configuration par défaut
if [ ! -f /etc/cbc-agent/config.yaml ]; then
    cat > /etc/cbc-agent/config.yaml << 'CONF'
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
CONF
fi

# Créer le service systemd
cat > /etc/systemd/system/cbc-agent.service << 'SERVICE'
[Unit]
Description=CBC Supervision Agent
After=network.target

[Service]
Type=simple
User=root
ExecStart=/usr/bin/cbc-agent --config /etc/cbc-agent/config.yaml
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SERVICE

# Activer et démarrer le service
systemctl daemon-reload
systemctl enable cbc-agent
systemctl start cbc-agent

exit 0
EOF
chmod +x "$BUILD_DIR/DEBIAN/postinst"

# Création du script pre-remove
cat > "$BUILD_DIR/DEBIAN/prerm" << 'EOF'
#!/bin/bash
set -e

# Arrêter et désactiver le service
if systemctl is-active --quiet cbc-agent; then
    systemctl stop cbc-agent
fi
systemctl disable cbc-agent

exit 0
EOF
chmod +x "$BUILD_DIR/DEBIAN/prerm"

# Construction du package DEB
dpkg-deb --build "$BUILD_DIR" "$PROJECT_ROOT/packaging/dist/cbc-agent_1.0.0_amd64.deb"

echo "✅ Package DEB construit: $PROJECT_ROOT/packaging/dist/cbc-agent_1.0.0_amd64.deb"

# Construction du package RPM (si rpmbuild est disponible)
if command -v rpmbuild &> /dev/null; then
    echo "🔨 Construction du package RPM..."
    
    RPM_BUILD_DIR="$PROJECT_ROOT/packaging/build/rpm"
    mkdir -p "$RPM_BUILD_DIR/SPECS"
    mkdir -p "$RPM_BUILD_DIR/SOURCES"
    mkdir -p "$RPM_BUILD_DIR/BUILD"
    mkdir -p "$RPM_BUILD_DIR/RPMS"
    mkdir -p "$RPM_BUILD_DIR/SRPMS"
    
    # Création du fichier spec RPM
    cat > "$RPM_BUILD_DIR/SPECS/cbc-agent.spec" << 'RPMSPEC'
Name: cbc-agent
Version: 1.0.0
Release: 1%{?dist}
Summary: CBC Supervision Agent
License: Apache-2.0
URL: https://github.com/cbc/cbc-supervision
Source0: %{name}-%{version}.tar.gz

BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)

Requires: python3, python3-psutil, python3-requests, python3-yaml

%description
Agent de supervision pour le système CBC Supervision Platform.
Collecte les métriques système et les envoie au serveur central.

%install
rm -rf $RPM_BUILD_ROOT
mkdir -p $RPM_BUILD_ROOT/usr/bin
mkdir -p $RPM_BUILD_ROOT/etc/cbc-agent
mkdir -p $RPM_BUILD_ROOT/etc/systemd/system

install -m 755 cbc-agent $RPM_BUILD_ROOT/usr/bin/cbc-agent

cat > $RPM_BUILD_ROOT/etc/cbc-agent/config.yaml << 'CONF'
server:
  url: https://localhost:8443
  enrollment_token: your-token-here

agent:
  heartbeat_interval: 30
  retry_interval: 60
  max_retries: 3
CONF

cat > $RPM_BUILD_ROOT/etc/systemd/system/cbc-agent.service << 'SERVICE'
[Unit]
Description=CBC Supervision Agent
After=network.target

[Service]
Type=simple
User=root
ExecStart=/usr/bin/cbc-agent --config /etc/cbc-agent/config.yaml
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SERVICE

%post
systemctl daemon-reload
systemctl enable cbc-agent
systemctl start cbc-agent

%preun
if [ $1 -eq 0 ]; then
    systemctl stop cbc-agent
    systemctl disable cbc-agent
fi

%files
/usr/bin/cbc-agent
/etc/cbc-agent/config.yaml
/etc/systemd/system/cbc-agent.service

%changelog
* $(date +'%a %b %d %Y') CBC Supervision <support@cbcam.cm> - 1.0.0-1
- Initial package
RPMSPEC
    
    # Copie de l'exécutable pour le build RPM
    if [ -f "$PROJECT_ROOT/dist/cbc-agent" ]; then
        cp "$PROJECT_ROOT/dist/cbc-agent" "$RPM_BUILD_DIR/BUILD/cbc-agent"
    fi
    
    # Construction du package RPM
    cd "$RPM_BUILD_DIR"
    rpmbuild --define "_topdir $RPM_BUILD_DIR" -bb SPECS/cbc-agent.spec
    
    # Copie du package RPM vers le répertoire dist
    cp "$RPM_BUILD_DIR/RPMS/x86_64/cbc-agent-1.0.0-1.x86_64.rpm" "$PROJECT_ROOT/packaging/dist/"
    
    echo "✅ Package RPM construit: $PROJECT_ROOT/packaging/dist/cbc-agent-1.0.0-1.x86_64.rpm"
else
    echo "⚠️  rpmbuild n'est pas installé, package RPM non construit"
fi

echo "🎉 Construction Linux terminée!"
