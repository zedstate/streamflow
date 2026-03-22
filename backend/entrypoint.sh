#!/bin/bash

# StreamFlow Entrypoint
# Starts Flask API directly

set -e

echo "[INFO] Starting StreamFlow Container: $(date)"

# Environment variables with defaults
API_HOST="${API_HOST:-0.0.0.0}"
API_PORT="${API_PORT:-5000}"
DEBUG_MODE="${DEBUG_MODE:-false}"
CONFIG_DIR="${CONFIG_DIR:-/app/data}"

# Export environment variables for the Flask application
export API_HOST API_PORT DEBUG_MODE CONFIG_DIR

# Deprecated: Old manual interval approach (kept for backward compatibility warnings)
if [ -n "$INTERVAL_SECONDS" ]; then
    echo "[WARNING] INTERVAL_SECONDS environment variable is deprecated."
    echo "[WARNING] The system now uses automated scheduling via the web API."
    echo "[WARNING] Please configure automation via the web interface or API endpoints."
fi

# Check if configuration files exist, create defaults if needed
echo "[INFO] Checking configuration files..."

# Ensure required directories exist (including the persisted data directory)
mkdir -p csv logs "$CONFIG_DIR"
echo "[INFO] Config directory: $CONFIG_DIR"

# Validate environment setup
echo "[INFO] Dispatcharr credentials will be configured via the Setup Wizard or loaded from the database."

# Start StreamFlow service
echo "[INFO] ============================================"
echo "[INFO] Starting StreamFlow Container"
echo "[INFO] ============================================"
echo "[INFO] Flask API: ${API_HOST}:${API_PORT}"
echo "[INFO] Debug mode: ${DEBUG_MODE}"
echo "[INFO] ============================================"
echo "[INFO] Access the web interface at http://localhost:${API_PORT}"
echo "[INFO] API documentation available at http://localhost:${API_PORT}/api/health"
echo "[INFO] ============================================"

# Start Flask API directly
echo "[INFO] Running configuration migrations..."
python3 scripts/migrate_to_sql.py

export PYTHONPATH=.

# Use exec to ensure Flask becomes PID 1 and receives signals properly
exec python3 apps/api/web_api.py --host "${API_HOST}" --port "${API_PORT}"
