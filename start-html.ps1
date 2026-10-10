$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$pythonPath = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Python environment missing. Create .venv and install requirements.txt first.' }
$running = $false
try { $session = Invoke-RestMethod -Uri 'http://127.0.0.1:8765/api/session' -TimeoutSec 2; $running = [bool]$session.token } catch {}
if (-not $running) {
    Start-Process -FilePath $pythonPath -ArgumentList 'web_bridge.py' -WorkingDirectory $PSScriptRoot -WindowStyle Hidden
    Start-Sleep -Milliseconds 700
}
Start-Process 'http://127.0.0.1:8765'
