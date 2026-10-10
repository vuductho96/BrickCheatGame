$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$pythonPath = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Run run.ps1 first.' }
& $pythonPath -m PyInstaller --noconfirm --clean --windowed --onedir --name ShopeePuzzleSolver --add-data 'config/settings.json:config' --exclude-module PyQt5 --exclude-module PyQt6 --exclude-module matplotlib --exclude-module scipy --exclude-module torch main.py
if ($LASTEXITCODE -ne 0) { throw 'Build failed. Install requirements-dev.txt first.' }
