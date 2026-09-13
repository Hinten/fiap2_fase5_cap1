$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot

Write-Host "Iniciando o backend em http://localhost:5000"
Push-Location $projectRoot
try {
    & ".venv\Scripts\python.exe" -m flask --app src.backend.app run --debug
}
finally {
    Pop-Location
}

