#!/bin/bash
# Railway Cron Job Status Checker
# Check if cron jobs have run recently using Railway CLI

echo "🔍 Checking Railway Cron Job Status..."
echo "=================================="

# Check if Railway CLI is installed
if ! command -v railway &> /dev/null; then
    echo "❌ Railway CLI not installed. Install with: npm install -g @railway/cli"
    exit 1
fi

# Function to check cron service logs
check_cron_service() {
    local service_name=$1
    local description=$2

    echo ""
    echo "📊 $description"
    echo "Service: $service_name"
    echo "Recent logs:"

    # Get recent logs (last 50 lines)
    railway logs --service="$service_name" --lines=50 2>/dev/null || {
        echo "❌ Could not fetch logs for $service_name"
        echo "   Make sure the service exists and you're logged in"
        return 1
    }

    echo "---"
}

# Check each cron service
check_cron_service "SurvivorPool-Odds-Cron" "Daily Odds Update Cron"
check_cron_service "SurvivorPool-Scores-Cron" "Score Updates Cron"
check_cron_service "SurvivorPool-Sheets-Cron" "Sheets Ingestion Cron"

echo ""
echo "💡 Tips:"
echo "  • Cron jobs should show recent execution logs"
echo "  • Look for exit codes: 0 = success, non-zero = failure"
echo "  • Odds cron runs daily at 8 AM EST"
echo "  • Scores cron runs hourly on Sundays"
echo "  • Sheets cron runs daily at 9 AM EST"
echo ""
echo "🔧 Manual trigger (if needed):"
echo "  railway run python cron/daily_odds_update.py"
echo "  railway run python cron/score_update.py"
echo "  railway run python cron/sheets_ingestion.py"