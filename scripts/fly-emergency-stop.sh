#!/usr/bin/env bash
# =============================================================================
# ForgeFlow AI - Emergency Stop Script
# =============================================================================
# Immediately stops ALL Fly.io machines for the forgeflow-api app.
# This halts all billing — machines are stopped but NOT destroyed.
# Data (volumes, DB) is preserved. Restart with: flyctl deploy
#
# Usage:
#   bash scripts/fly-emergency-stop.sh
#   powershell -File scripts/fly-emergency-stop.ps1
# =============================================================================
set -euo pipefail

APP="${1:-forgeflow-api}"

echo "=== ForgeFlow Emergency Stop ==="
echo "App: $APP"
echo ""

# List running machines
echo "Current machines:"
flyctl machines list --app "$APP" 2>/dev/null || {
  echo "No machines found or app does not exist."
  exit 0
}

echo ""
echo "Stopping all machines..."
MACHINES=$(flyctl machines list --app "$APP" -q 2>/dev/null)

if [ -z "$MACHINES" ]; then
  echo "No machines to stop."
  exit 0
fi

for MACHINE_ID in $MACHINES; do
  echo "  Stopping $MACHINE_ID..."
  flyctl machines stop "$MACHINE_ID" --app "$APP" 2>&1
done

echo ""
echo "=== All machines stopped ==="
echo "To restart: flyctl deploy --app $APP"
