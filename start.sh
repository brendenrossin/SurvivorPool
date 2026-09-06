#!/bin/bash
echo "🚀 Starting app with PORT=$PORT"
echo "📝 Environment check:"
echo "  PORT: $PORT"
echo "  DATABASE_URL: ${DATABASE_URL:0:30}..."

# Initialize database first
echo "🗄️ Initializing database..."
python init_db_railway.py

# Apply odds columns migration
echo "🎰 Applying odds integration migration..."
python scripts/railway_migration.py
if [ $? -eq 0 ]; then
    echo "✅ Odds migration completed successfully"
else
    echo "BOOT-WARNING: odds column migration failed; odds features may be degraded"
fi

# Default port if not set
if [ -z "$PORT" ]; then
    PORT=8080
    echo "⚠️  PORT not set, using default: $PORT"
fi

# NOTE: a mock-data population branch used to sit here. It called
# railway_populate_mock.py and backfill_historical.py from the repo root, but
# both moved into scripts/ on 2025-09-30 and this file was never updated, so it
# had failed silently ever since behind "continuing anyway". Its trigger was
# `player_count < 20 or pick_count < 50`, which is TRUE for a fresh or a
# newly-rolled-over season - so had the paths ever been corrected it would have
# seeded randomised players and picks into a live pool. It also ran
# jobs/update_scores.py twice, on top of the run further down. Deleted rather
# than repaired: nothing should be able to invent entrants on boot.

# Try to ingest real data from Google Sheets if OAuth is configured
echo "📊 Attempting real data ingestion from Google Sheets..."
python jobs/ingest_personal_sheets.py
if [ $? -eq 0 ]; then
    echo "✅ Real data ingested successfully from Google Sheets"
else
    echo "BOOT-WARNING: sheet ingestion failed on startup; serving whatever is already in the database"
fi

# Always ensure game winners are set with improved logic
echo "🏆 Ensuring game winners are set with improved completion detection..."
python -c "
from jobs.update_scores import ScoreUpdater
from api.database import SessionLocal

print('Final check: Updating all weeks with improved game completion detection...')
updater = ScoreUpdater()

# Run the full score update process which includes:
# - Fetching scores for current week
# - Backfilling all previous weeks
# - Auto-eliminating players with missing picks
# - Finalizing stuck games
print('🔄 Running full score update on startup...')
updater.run(fetch_odds=False)
print('✅ Full score update completed on startup')
"

echo "🚀 All data processing complete"
echo "🎯 Starting Streamlit on port $PORT"

exec streamlit run app/main.py \
    --server.port=$PORT \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --server.enableCORS=false \
    --server.enableXsrfProtection=false