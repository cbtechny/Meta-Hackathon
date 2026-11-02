$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$pythonPath = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Create .venv and install requirements.txt first; see README.md.'
}
& $pythonPath -m uvicorn counterpilot.app:app --host 127.0.0.1 --port 8000 --no-access-log
