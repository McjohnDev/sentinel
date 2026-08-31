# Run the CBC agent from source against the local Docker stack (http://127.0.0.1:8443).
$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $PSScriptRoot
Set-Location $Repo

$env:PYTHONPATH = "$Repo;$Repo\agent\src"

python -m pip install -q -r "$Repo\shared\requirements.txt" -r "$Repo\agent\requirements.txt"
python "$Repo\agent\src\agent.py" "$Repo\agent\config.lab.yaml"
