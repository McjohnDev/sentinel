#!/bin/bash
# Script d'installation universel pour l'agent CBC Supervision
# Compatible avec Linux, macOS et Windows (via Git Bash/WSL)
# Supporte le téléchargement depuis un serveur central

set -e

# Configuration du serveur de distribution
DOWNLOAD_BASE_URL="${DOWNLOAD_BASE_URL:-https://download.cbc-cam.cm/cbc-agent}"
VERSION="${VERSION:-1.0.0}"
OFFLINE_MODE="${OFFLINE_MODE:-false}"

# Détection de la plateforme
detect_platform() {
    case "$(uname -s)" in
        Linux*)     PLATFORM="linux";;
        Darwin*)    PLATFORM="macos";;
        CYGWIN*)    PLATFORM="windows";;
        MINGW*)     PLATFORM="windows";;
        MSYS*)      PLATFORM="windows";;
        *)          PLATFORM="unknown";;
    esac
    echo "$PLATFORM"
}

# Téléchargement du package depuis le serveur
download_package() {
    local platform=$1
    local package_url=""
    
    # Mode offline: utiliser les packages locaux
    if [ "$OFFLINE_MODE" = "true" ]; then
        echo "📦 Mode offline: utilisation des packages locaux" >&2
        
        case "$platform" in
            "linux")
                if command -v apt-get &> /dev/null && [ -f "agent/packaging/dist/cbc-agent_${VERSION}_amd64.deb" ]; then
                    echo "agent/packaging/dist/cbc-agent_${VERSION}_amd64.deb"
                elif (command -v yum &> /dev/null || command -v dnf &> /dev/null) && [ -f "agent/packaging/dist/cbc-agent-${VERSION}-1.x86_64.rpm" ]; then
                    echo "agent/packaging/dist/cbc-agent-${VERSION}-1.x86_64.rpm"
                else
                    echo "❌ Package local non trouvé" >&2
                    exit 1
                fi
                ;;
            "macos")
                if [ -f "agent/packaging/dist/cbc-agent-${VERSION}.pkg" ]; then
                    echo "agent/packaging/dist/cbc-agent-${VERSION}.pkg"
                else
                    echo "❌ Package local non trouvé" >&2
                    exit 1
                fi
                ;;
            "windows")
                if [ -f "agent/packaging/dist/cbc-agent-${VERSION}.msi" ]; then
                    echo "agent/packaging/dist/cbc-agent-${VERSION}.msi"
                else
                    echo "❌ Package local non trouvé" >&2
                    exit 1
                fi
                ;;
        esac
        return
    fi
    
    # Mode online: télécharger depuis le serveur
    case "$platform" in
        "linux")
            if command -v apt-get &> /dev/null; then
                package_url="${DOWNLOAD_BASE_URL}/cbc-agent_${VERSION}_amd64.deb"
            elif command -v yum &> /dev/null || command -v dnf &> /dev/null; then
                package_url="${DOWNLOAD_BASE_URL}/cbc-agent-${VERSION}-1.x86_64.rpm"
            else
                package_url="${DOWNLOAD_BASE_URL}/cbc-agent-${VERSION}-linux.tar.gz"
            fi
            ;;
        "macos")
            package_url="${DOWNLOAD_BASE_URL}/cbc-agent-${VERSION}.pkg"
            ;;
        "windows")
            package_url="${DOWNLOAD_BASE_URL}/cbc-agent-${VERSION}.msi"
            ;;
        *)
            echo "❌ Plateforme non supportée"
            exit 1
            ;;
    esac
    
    echo "📥 Téléchargement depuis: $package_url"
    
    local temp_file=$(mktemp)
    if command -v curl &> /dev/null; then
        curl -fsSL "$package_url" -o "$temp_file"
    elif command -v wget &> /dev/null; then
        wget -q "$package_url" -O "$temp_file"
    else
        echo "❌ Ni curl ni wget n'est disponible"
        exit 1
    fi
    
    echo "$temp_file"
}

# Installation pour Linux
install_linux() {
    echo "🐧 Installation pour Linux..."
    
    # Télécharger le package
    local package_file=$(download_package "linux")
    
    # Vérification des dépendances
    if command -v apt-get &> /dev/null; then
        # Debian/Ubuntu
        echo "📦 Installation des dépendances..."
        sudo apt-get update
        sudo apt-get install -y python3 python3-pip python3-psutil python3-requests python3-yaml
        
        # Installation du package DEB
        echo "📦 Installation du package DEB..."
        sudo dpkg -i "$package_file"
        sudo apt-get install -f  # Pour résoudre les dépendances
    elif command -v yum &> /dev/null || command -v dnf &> /dev/null; then
        # RedHat/CentOS/Fedora
        echo "📦 Installation des dépendances..."
        if command -v dnf &> /dev/null; then
            sudo dnf install -y python3 python3-pip
        else
            sudo yum install -y python3 python3-pip
        fi
        sudo pip3 install psutil requests pyyaml
        
        # Installation du package RPM
        echo "📦 Installation du package RPM..."
        sudo rpm -i "$package_file"
    else
        # Installation manuelle
        echo "📦 Installation manuelle..."
        sudo pip3 install psutil requests pyyaml
        
        mkdir -p /usr/local/bin
        sudo cp "$package_file" /usr/local/bin/cbc-agent
        sudo chmod +x /usr/local/bin/cbc-agent
    fi
    
    # Nettoyage
    rm -f "$package_file"
    
    echo "✅ Installation terminée!"
    echo "📝 Configuration: /etc/cbc-agent/config.yaml"
    echo "🔧 Service: sudo systemctl status cbc-agent"
}

# Installation pour macOS
install_macos() {
    echo "🍎 Installation pour macOS..."
    
    # Télécharger le package
    local package_file=$(download_package "macos")
    
    # Vérification des dépendances
    if ! command -v brew &> /dev/null; then
        echo "⚠️  Homebrew n'est pas installé. Installation..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    fi
    
    echo "📦 Installation des dépendances..."
    brew install python3
    pip3 install psutil requests pyyaml
    
    # Installation du package PKG
    echo "📦 Installation du package PKG..."
    sudo installer -pkg "$package_file" -target /
    
    # Nettoyage
    rm -f "$package_file"
    
    echo "✅ Installation terminée!"
    echo "📝 Configuration: /etc/cbc-agent/config.yaml"
    echo "🔧 Service: sudo launchctl list | grep cbc-agent"
}

# Installation pour Windows
install_windows() {
    echo "🪟 Installation pour Windows..."
    
    # Télécharger le package
    local package_file=$(download_package "windows")
    
    # Vérification de Python
    if ! command -v python &> /dev/null; then
        echo "⚠️  Python n'est pas installé. Veuillez l'installer depuis https://python.org"
        exit 1
    fi
    
    echo "📦 Installation des dépendances..."
    pip install psutil requests pyyaml
    
    # Installation du package MSI
    if [[ "$package_file" == *.msi ]]; then
        echo "📦 Installation du package MSI..."
        msiexec /i "$package_file" /quiet /norestart
    else
        echo "📦 Installation de l'exécutable..."
        mkdir -p "C:/Program Files/CBC Agent"
        cp "$package_file" "C:/Program Files/CBC Agent/"
        
        # Création du service Windows
        if command -v sc &> /dev/null; then
            sc create CBCAgent binPath= "C:/Program Files/CBC Agent/cbc-agent.exe --config C:/ProgramData/CBC Agent/config.yaml" start= auto
            sc start CBCAgent
        fi
    fi
    
    # Nettoyage
    rm -f "$package_file"
    
    echo "✅ Installation terminée!"
    echo "📝 Configuration: C:/Program Files/CBC Agent/config.yaml"
    echo "🔧 Service: sc query CBCAgent"
}

# Fonction principale
main() {
    echo "🚀 CBC Supervision Agent - Installation"
    echo "======================================"
    
    PLATFORM=$(detect_platform)
    echo "📌 Plateforme détectée: $PLATFORM"
    
    if [ "$PLATFORM" = "unknown" ]; then
        echo "⚠️  Plateforme non reconnue"
        exit 1
    elif [ "$PLATFORM" = "linux" ]; then
        install_linux
    elif [ "$PLATFORM" = "macos" ]; then
        install_macos
    elif [ "$PLATFORM" = "windows" ]; then
        install_windows
    fi
    
    echo ""
    echo "🎉 Installation terminée avec succès!"
    echo ""
    echo "📝 Étapes suivantes:"
    echo "1. Configurez l'agent en éditant le fichier de configuration"
    echo "2. Obtenez un token d'enrôlement depuis le serveur"
    echo "3. Redémarrez le service pour appliquer la configuration"
    echo ""
    echo "📚 Documentation: https://github.com/cbc/cbc-supervision"
}

main "$@"
