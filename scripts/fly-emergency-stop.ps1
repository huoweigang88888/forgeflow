# =============================================================================
# ForgeFlow AI - Emergency Stop (PowerShell)
# =============================================================================
# Immediately stops ALL Fly.io machines. No billing after this point.
# Data preserved. Restart with: flyctl deploy --app $APP
# =============================================================================
param(
    [string]$App = "forgeflow-api"
)

Write-Host "=== ForgeFlow Emergency Stop ===" -ForegroundColor Red
Write-Host "App: $App"
Write-Host ""

Write-Host "Stopping all machines..." -ForegroundColor Yellow
$machines = flyctl machines list --app $App -q 2>$null

if (-not $machines) {
    Write-Host "No machines to stop." -ForegroundColor Green
    exit 0
}

foreach ($id in $machines -split "`n") {
    if ($id.Trim()) {
        Write-Host "  Stopping $id..."
        flyctl machines stop $id.Trim() --app $App
    }
}

Write-Host ""
Write-Host "=== All machines stopped ===" -ForegroundColor Green
Write-Host "To restart: flyctl deploy --app $App"
Write-Host "To completely destroy: flyctl apps destroy $App"
