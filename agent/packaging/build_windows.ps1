# Script de build pour Windows (MSI)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

Write-Host "🔨 Construction de l'agent pour Windows..." -ForegroundColor Green

# Nettoyage
Write-Host "🧹 Nettoyage..." -ForegroundColor Yellow
Remove-Item -Path "$ProjectRoot\packaging\build" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -Path "$ProjectRoot\packaging\dist" -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path "$ProjectRoot\packaging\build" -Force | Out-Null
New-Item -ItemType Directory -Path "$ProjectRoot\packaging\dist" -Force | Out-Null

# Construction de l'exécutable
Write-Host "📦 Construction de l'exécutable avec PyInstaller..." -ForegroundColor Yellow
Set-Location $ProjectRoot
pyinstaller --clean --noconfirm packaging\agent.spec

# Construction du package MSI
Write-Host "🔨 Construction du package MSI..." -ForegroundColor Yellow

$MSIBuildDir = "$ProjectRoot\packaging\build\msi"
New-Item -ItemType Directory -Path "$MSIBuildDir\Program Files\CBC Agent" -Force | Out-Null
New-Item -ItemType Directory -Path "$MSIBuildDir\ProgramData\CBC Agent" -Force | Out-Null

# Copie de l'exécutable
if (Test-Path "$ProjectRoot\dist\cbc-agent.exe") {
    Copy-Item "$ProjectRoot\dist\cbc-agent.exe" "$MSIBuildDir\Program Files\CBC Agent\cbc-agent.exe"
}

# Création du fichier de configuration
$ConfigContent = @"
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
  file: C:\ProgramData\CBC Agent\agent.log
  max_size: 10485760
  backup_count: 5
"@
Set-Content -Path "$MSIBuildDir\Program Files\CBC Agent\config.yaml" -Value $ConfigContent

# Création du script d'installation WiX
$WxsContent = @"
<?xml version="1.0" encoding="UTF-8"?>
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
            <Directory Id="ProgramDataFolder">
                <Directory Id="DATADIR" Name="CBC Agent" />
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
"@
Set-Content -Path "$MSIBuildDir\agent.wxs" -Value $WxsContent

# Vérification de WiX
if (Get-Command candle -ErrorAction SilentlyContinue) {
    Write-Host "🔨 Construction du package MSI avec WiX..." -ForegroundColor Yellow
    
    # Compilation avec candle
    candle "$MSIBuildDir\agent.wxs" -out "$MSIBuildDir\agent.wixobj" -ext WixUtilExtension
    
    # Linking avec light
    light "$MSIBuildDir\agent.wixobj" -out "$ProjectRoot\packaging\dist\cbc-agent-1.0.0.msi" -ext WixUtilExtension
    
    Write-Host "✅ Package MSI construit: $ProjectRoot\packaging\dist\cbc-agent-1.0.0.msi" -ForegroundColor Green
} else {
    Write-Host "⚠️  WiX Toolset n'est pas installé. Package MSI non construit." -ForegroundColor Yellow
    Write-Host "   Installez WiX Toolset depuis: https://wixtoolset.org/" -ForegroundColor Cyan
}

Write-Host "🎉 Construction Windows terminée!" -ForegroundColor Green
