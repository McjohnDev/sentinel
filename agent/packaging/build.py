#!/usr/bin/env python3
"""
Script de build multi-plateforme pour l'agent CBC Supervision.
Supporte Linux (DEB/RPM), macOS (PKG) et Windows (MSI).
"""

import os
import sys
import platform
import subprocess
import shutil
from pathlib import Path


class AgentBuilder:
    """Builder multi-plateforme pour l'agent."""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.build_dir = self.project_root / "packaging" / "build"
        self.dist_dir = self.project_root / "packaging" / "dist"
        self.platform = platform.system().lower()
        
    def clean(self):
        """Nettoie les répertoires de build."""
        print("🧹 Nettoyage des répertoires de build...")
        if self.build_dir.exists():
            shutil.rmtree(self.build_dir)
        if self.dist_dir.exists():
            shutil.rmtree(self.dist_dir)
        self.build_dir.mkdir(parents=True, exist_ok=True)
        self.dist_dir.mkdir(parents=True, exist_ok=True)
        print("✅ Nettoyage terminé")
    
    def build_executable(self):
        """Construit l'exécutable avec PyInstaller."""
        print(f"🔨 Construction de l'exécutable pour {self.platform}...")
        
        spec_file = self.project_root / "packaging" / "agent.spec"
        
        cmd = [
            "pyinstaller",
            "--clean",
            "--noconfirm",
            str(spec_file)
        ]
        
        try:
            subprocess.run(cmd, check=True, cwd=self.project_root)
            print("✅ Exécutable construit avec succès")
        except subprocess.CalledProcessError as e:
            print(f"❌ Erreur lors de la construction: {e}")
            sys.exit(1)
    
    def build_linux_package(self):
        """Construit les packages Linux (DEB/RPM)."""
        print("📦 Construction des packages Linux...")
        
        if self.platform != "linux":
            print("⚠️  Ce script doit être exécuté sur Linux pour construire des packages Linux")
            return
        
        # Construction DEB
        self._build_deb()
        
        # Construction RPM
        self._build_rpm()
    
    def _build_deb(self):
        """Construit un package DEB pour Debian/Ubuntu."""
        print("🔨 Construction du package DEB...")
        
        deb_dir = self.build_dir / "deb"
        deb_dir.mkdir(parents=True, exist_ok=True)
        
        # Structure du package DEB
        debian_dir = deb_dir / "DEBIAN"
        debian_dir.mkdir(parents=True, exist_ok=True)
        
        # Copie de l'exécutable
        usr_bin = deb_dir / "usr" / "bin"
        usr_bin.mkdir(parents=True, exist_ok=True)
        
        dist_dir = self.project_root / "dist"
        if (dist_dir / "cbc-agent").exists():
            shutil.copy(dist_dir / "cbc-agent", usr_bin / "cbc-agent")
        elif (dist_dir / "cbc-agent.exe").exists():
            shutil.copy(dist_dir / "cbc-agent.exe", usr_bin / "cbc-agent")
        
        # Création du fichier de contrôle
        control_file = debian_dir / "control"
        control_content = """Package: cbc-agent
Version: 1.0.0
Section: utils
Priority: optional
Architecture: amd64
Maintainer: CBC Supervision <support@cbcam.cm>
Description: CBC Supervision Agent
 Agent de supervision pour le système CBC Supervision Platform.
 Collecte les métriques système et les envoie au serveur central.
Depends: python3, python3-psutil, python3-requests, python3-yaml
"""
        control_file.write_text(control_content)
        
        # Création du script post-install
        postinst = debian_dir / "postinst"
        postinst_content = """#!/bin/bash
set -e

# Créer le répertoire de configuration
mkdir -p /etc/cbc-agent

# Créer le fichier de configuration par défaut
if [ ! -f /etc/cbc-agent/config.yaml ]; then
    cat > /etc/cbc-agent/config.yaml << EOF
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
EOF
fi

# Créer le service systemd
cat > /etc/systemd/system/cbc-agent.service << EOF
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
EOF

# Activer et démarrer le service
systemctl daemon-reload
systemctl enable cbc-agent
systemctl start cbc-agent

exit 0
"""
        postinst.write_text(postinst_content)
        postinst.chmod(0o755)
        
        # Construction du package DEB
        cmd = ["dpkg-deb", "--build", str(deb_dir), str(self.dist_dir / "cbc-agent_1.0.0_amd64.deb")]
        try:
            subprocess.run(cmd, check=True)
            print("✅ Package DEB construit avec succès")
        except subprocess.CalledProcessError as e:
            print(f"❌ Erreur lors de la construction DEB: {e}")
    
    def _build_rpm(self):
        """Construit un package RPM pour RedHat/CentOS."""
        print("🔨 Construction du package RPM...")
        
        rpm_dir = self.build_dir / "rpm"
        rpm_dir.mkdir(parents=True, exist_ok=True)
        
        # Structure du package RPM
        spec_file = rpm_dir / "cbc-agent.spec"
        spec_content = """Name: cbc-agent
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

install -m 755 ./cbc-agent "$RPM_BUILD_ROOT/usr/bin/cbc-agent"

cat > $RPM_BUILD_ROOT/etc/cbc-agent/config.yaml << EOF
server:
  url: https://localhost:8443
  enrollment_token: your-token-here

agent:
  heartbeat_interval: 30
  retry_interval: 60
  max_retries: 3
EOF

cat > $RPM_BUILD_ROOT/etc/systemd/system/cbc-agent.service << EOF
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
EOF

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
* Mon Aug 04 2026 CBC Supervision <support@cbcam.cm> - 1.0.0-1
- Initial package
"""
        spec_file.write_text(spec_content)
        
        # Créer un lien symbolique vers un chemin sans espaces
        import tempfile
        temp_dir = Path(tempfile.mkdtemp(prefix="cbc-agent-rpm-"))
        temp_link = temp_dir / "cbc-agent"
        
        # Copie de l'exécutable pour le build RPM
        dist_dir = self.project_root / "dist"
        if (dist_dir / "cbc-agent").exists():
            shutil.copy(dist_dir / "cbc-agent", temp_link)
        
        # Créer la structure de répertoires RPM dans le temp dir
        (temp_dir / "SOURCES").mkdir(exist_ok=True)
        (temp_dir / "SPECS").mkdir(exist_ok=True)
        (temp_dir / "BUILD").mkdir(exist_ok=True)
        (temp_dir / "RPMS").mkdir(exist_ok=True)
        (temp_dir / "SRPMS").mkdir(exist_ok=True)
        
        # Copier le spec file dans SPECS
        shutil.copy(spec_file, temp_dir / "SPECS" / "cbc-agent.spec")
        
        # Copier l'exécutable dans BUILD
        shutil.copy(temp_link, temp_dir / "BUILD" / "cbc-agent")
        
        # Construction du package RPM
        try:
            cmd = [
                "rpmbuild",
                "--define", f"_topdir {temp_dir}",
                "-bb", str(temp_dir / "SPECS" / "cbc-agent.spec")
            ]
            subprocess.run(cmd, check=True, cwd=temp_dir / "BUILD")
            
            # Copie du package RPM vers le répertoire dist
            rpms = list(temp_dir.glob("RPMS/**/*.rpm"))
            if rpms:
                shutil.copy(rpms[0], self.dist_dir / rpms[0].name)
                print(f"✅ Package RPM construit: {self.dist_dir / rpms[0].name}")
            else:
                print("⚠️  Package RPM non trouvé dans le répertoire de build")
        except subprocess.CalledProcessError as e:
            print(f"❌ Erreur lors de la construction RPM: {e}")
        except FileNotFoundError:
            print("⚠️  rpmbuild n'est pas installé. Package RPM non construit.")
        finally:
            # Nettoyage du répertoire temporaire
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    def build_macos_package(self):
        """Construit un package PKG pour macOS."""
        print("📦 Construction du package macOS...")
        
        if self.platform != "darwin":
            print("⚠️  Ce script doit être exécuté sur macOS pour construire des packages macOS")
            return
        
        pkg_dir = self.build_dir / "pkg"
        pkg_dir.mkdir(parents=True, exist_ok=True)
        
        # Structure du package PKG
        root_dir = pkg_dir / "root"
        root_dir.mkdir(parents=True, exist_ok=True)
        
        # Copie de l'exécutable
        usr_local_bin = root_dir / "usr" / "local" / "bin"
        usr_local_bin.mkdir(parents=True, exist_ok=True)
        
        dist_dir = self.project_root / "dist"
        if (dist_dir / "cbc-agent").exists():
            shutil.copy(dist_dir / "cbc-agent", usr_local_bin / "cbc-agent")
            (usr_local_bin / "cbc-agent").chmod(0o755)
        
        # Création du fichier de configuration
        etc_cbc = root_dir / "etc" / "cbc-agent"
        etc_cbc.mkdir(parents=True, exist_ok=True)
        
        config_file = etc_cbc / "config.yaml"
        config_content = """server:
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
"""
        config_file.write_text(config_content)
        
        # Création du launchd plist
        launchd_dir = root_dir / "Library" / "LaunchDaemons"
        launchd_dir.mkdir(parents=True, exist_ok=True)
        
        plist_file = launchd_dir / "com.cbc.agent.plist"
        plist_content = """<?xml version="1.0" encoding="UTF-8"?>
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
</dict>
</plist>
"""
        plist_file.write_text(plist_content)
        
        # Construction du package PKG
        cmd = [
            "pkgbuild",
            "--root", str(root_dir),
            "--identifier", "com.cbc.agent",
            "--version", "1.0.0",
            str(self.dist_dir / "cbc-agent-1.0.0.pkg")
        ]
        
        try:
            subprocess.run(cmd, check=True)
            print("✅ Package PKG construit avec succès")
        except subprocess.CalledProcessError as e:
            print(f"❌ Erreur lors de la construction PKG: {e}")
    
    def build_windows_package(self):
        """Construit un package MSI pour Windows."""
        print("📦 Construction du package Windows...")
        
        if self.platform != "windows":
            print("⚠️  Ce script doit être exécuté sur Windows pour construire des packages Windows")
            return
        
        msi_dir = self.build_dir / "msi"
        msi_dir.mkdir(parents=True, exist_ok=True)
        
        # Structure du package MSI
        program_files = msi_dir / "Program Files" / "CBC Agent"
        program_files.mkdir(parents=True, exist_ok=True)
        
        # Copie de l'exécutable
        dist_dir = self.project_root / "dist"
        if (dist_dir / "cbc-agent.exe").exists():
            shutil.copy(dist_dir / "cbc-agent.exe", program_files / "cbc-agent.exe")
        
        # Création du fichier de configuration
        config_file = program_files / "config.yaml"
        config_content = """server:
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
  file: C:\\ProgramData\\CBC Agent\\agent.log
  max_size: 10485760
  backup_count: 5
"""
        config_file.write_text(config_content)
        
        # Création du script d'installation WiX
        wxs_file = msi_dir / "agent.wxs"
        wxs_content = """<?xml version="1.0" encoding="UTF-8"?>
<Wix xmlns="http://schemas.microsoft.com/wix/2006/wi">
    <Product Id="*" Name="CBC Agent" Language="1033" Version="1.0.0.0" 
             Manufacturer="CBC Supervision" UpgradeCode="12345678-1234-1234-1234-123456789012">
        <Package InstallerVersion="200" Compressed="yes" InstallScope="perMachine" />
        
        <MajorUpgrade DowngradeErrorMessage="A newer version is already installed." />
        <MediaTemplate EmbedCab="yes" />
        
        <Feature Id="ProductFeature" Title="CBC Agent" Level="1">
            <ComponentGroupRef Id="ProductComponents" />
            <ComponentRef Id="ServiceComponent" />
        </Feature>
        
        <DirectoryRef Id="TARGETDIR">
            <Component Id="ServiceComponent" Guid="*">
                <ServiceInstall Id="CBCAgentService"
                                Type="ownProcess"
                                Vital="yes"
                                Name="CBCAgent"
                                DisplayName="CBC Supervision Agent"
                                Description="CBC Supervision Agent - System Monitoring"
                                Start="auto"
                                Account="LocalSystem"
                                ErrorControl="ignore"
                                Interactive="no">
                    <ServiceConfig DelayedAutoStart="yes" />
                </ServiceInstall>
                <ServiceControl Id="StartService" Start="install" Stop="both" Remove="uninstall" Name="CBCAgent" Wait="yes" />
            </Component>
        </DirectoryRef>
    </Product>
    
    <Fragment>
        <Directory Id="TARGETDIR" Name="SourceDir">
            <Directory Id="ProgramFilesFolder">
                <Directory Id="INSTALLFOLDER" Name="CBC Agent" />
            </Directory>
        </Directory>
    </Fragment>
    
    <Fragment>
        <ComponentGroup Id="ProductComponents" Directory="INSTALLFOLDER">
            <Component Id="MainExecutable" Guid="*">
                <File Id="AgentExe" Source="cbc-agent.exe" />
            </Component>
            <Component Id="ConfigFile" Guid="*">
                <File Id="ConfigYaml" Source="config.yaml" />
            </Component>
        </ComponentGroup>
    </Fragment>
</Wix>
"""
        wxs_file.write_text(wxs_content)
        
        print("✅ Fichiers MSI créés (construction avec WiX requise)")
    
    def build_all(self):
        """Construit tous les packages pour la plateforme actuelle."""
        print(f"🚀 Construction de tous les packages pour {self.platform}...")
        
        self.clean()
        self.build_executable()
        
        if self.platform == "linux":
            self.build_linux_package()
        elif self.platform == "darwin":
            self.build_macos_package()
        elif self.platform == "windows":
            self.build_windows_package()
        
        print(f"✅ Construction terminée. Packages disponibles dans {self.dist_dir}")


if __name__ == "__main__":
    builder = AgentBuilder()
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        if command == "clean":
            builder.clean()
        elif command == "exe":
            builder.build_executable()
        elif command == "deb":
            builder.build_linux_package()
        elif command == "rpm":
            builder._build_rpm()
        elif command == "pkg":
            builder.build_macos_package()
        elif command == "msi":
            builder.build_windows_package()
        elif command == "all":
            builder.build_all()
        else:
            print(f"Commande inconnue: {command}")
            print("Commandes disponibles: clean, exe, deb, rpm, pkg, msi, all")
    else:
        builder.build_all()
