$ErrorActionPreference='Stop'
try {
    $session=Invoke-RestMethod 'http://127.0.0.1:8765/api/session' -TimeoutSec 2
    Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8765/api/auto' -Headers @{'X-Session-Token'=$session.token} -ContentType 'application/json' -Body '{"action":"stop"}' -TimeoutSec 5 | Out-Null
    Write-Host 'Auto stopped. Live screen remains available.'
} catch { Write-Host 'Local app is not running.' }
