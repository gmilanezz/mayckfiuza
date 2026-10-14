$ErrorActionPreference = "Stop"
Set-Location "$PSScriptRoot\frontend"

if (-not (Test-Path "node_modules")) {
    Write-Host "Instalando dependencias do frontend..."
    npm install
}

npm run dev
