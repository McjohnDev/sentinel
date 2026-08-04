#!/bin/bash
# Script de build pour macOS (PKG)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "🔨 Construction de l'agent pour macOS..."

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

# Construction du package PKG
echo "🔨 Construction du package PKG..."

PKG_BUILD_DIR="$PROJECT_ROOT/packaging/build/pkg"
mkdir -p "$PKG_BUILD_DIR/root/usr/local/bin"
mkdir -p "$PKG_BUILD_DIR/root/etc/cbc-agent"
mkdir -p "$PKG_BUILD_DIR/root/Library/LaunchDaemons"

# Copie de l'exécutable
if [ -f "$PROJECT_ROOT/dist/cbc-agent" ]; then
    cp "$PROJECT_ROOT/dist/cbc-agent" "$PKG_BUILD_DIR/root/usr/local/bin/cbc-agent"
    chmod +x "$PKG_BUILD_DIR/root/usr/local/bin/cbc-agent"
fi

# Création du fichier de configuration
cat > "$PKG_BUILD_DIR/root/etc/cbc-agent/config.yaml" << 'CONF'
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

# Création du launchd plist
cat > "$PKG_BUILD_DIR/root/Library/LaunchDaemons/com.cbc.agent.plist" << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.cbc.agent</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/cbc-agent</string>
        <string>--config</string>
        <string>/etc/cbc-agent/config.yaml</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/var/log/cbc-agent/agent.log</string>
    <key>StandardErrorPath</key>
    <string>/var/log/cbc-agent/agent-error.log</string>
</dict>
</plist>
PLIST

# Création du script post-install
cat > "$PKG_BUILD_DIR/scripts/postinstall" << 'POSTINSTALL'
#!/bin/bash
set -e

# Créer le répertoire de logs
mkdir -p /var/log/cbc-agent
chmod 755 /var/log/cbc-agent

# Charger le launchd plist
launchctl load /Library/LaunchDaemons/com.cbc.agent.plist

# Démarrer le service
launchctl start com.cbc.agent

exit 0
POSTINSTALL
chmod +x "$PKG_BUILD_DIR/scripts/postinstall"

# Création du script pre-remove
cat > "$PKG_BUILD_DIR/scripts/preinstall" << 'PREINSTALL'
#!/bin/bash
set -e

# Arrêter le service s'il tourne
if launchctl list | grep -q "com.cbc.agent"; then
    launchctl stop com.cbc.agent
    launchctl unload /Library/LaunchDaemons/com.cbc.agent.plist
fi

exit 0
PREINSTALL
chmod +x "$PKG_BUILD_DIR/scripts/preinstall"

# Construction du package PKG
pkgbuild \
    --root "$PKG_BUILD_DIR/root" \
    --scripts "$PKG_BUILD_DIR/scripts" \
    --identifier "com.cbc.agent" \
    --version "1.0.0" \
    --install-location "/" \
    "$PROJECT_ROOT/packaging/dist/cbc-agent-1.0.0.pkg"

echo "✅ Package PKG construit: $PROJECT_ROOT/packaging/dist/cbc-agent-1.0.0.pkg"
echo "🎉 Construction macOS terminée!"
