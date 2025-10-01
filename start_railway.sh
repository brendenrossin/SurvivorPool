#!/bin/bash
# Railway startup wrapper - selects correct startup script based on environment
# This allows dev/staging/prod to use different startup scripts

# Default to production startup script
SCRIPT="${RAILWAY_START_SCRIPT:-start.sh}"

echo "🚂 Railway startup wrapper"
echo "📝 Selected script: $SCRIPT"

# Execute the selected startup script
exec bash "$SCRIPT"
