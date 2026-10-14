$ErrorActionPreference = "Stop"
Set-Location "$PSScriptRoot\backend"

# Desenvolvimento local usa SQLite. Evita herdar DATABASE_URL/Neon do sistema.
Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Criando ambiente virtual do backend..."
    python -m venv .venv
}

& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt
& ".\.venv\Scripts\python.exe" -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
