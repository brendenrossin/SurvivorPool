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
    echo "⚠️ Odds migration failed, continuing anyway"
fi

# Default port if not set
if [ -z "$PORT" ]; then
    PORT=8080
    echo "⚠️  PORT not set, using default: $PORT"
fi

echo "🎯 Starting Streamlit on port $PORT"

# Check if database needs initial data population
echo "📊 Checking if database needs initial data..."
python -c "
from api.database import SessionLocal
from api.models import Player, Pick
try:
    db = SessionLocal()
    player_count = db.query(Player).count()
    pick_count = db.query(Pick).count()
    db.close()

    print(f'📊 Current database state: {player_count} players, {pick_count} picks')

    if player_count < 20 or pick_count < 50:
        print('🆕 Database needs comprehensive data, will populate...')
        exit(1)
    else:
        print(f'✅ Database has sufficient data ({player_count} players, {pick_count} picks)')
        exit(0)
except Exception as e:
    print(f'⚠️ Database check failed: {e}, will try to populate anyway...')
    exit(1)
"

if [ $? -eq 1 ]; then
    echo "🔄 Populating database with mock data..."
    python railway_populate_mock.py
    if [ $? -eq 0 ]; then
        echo "✅ Mock data created successfully"
    else
        echo "⚠️ Mock data creation failed, continuing anyway"
    fi

    echo "🏈 Fetching NFL games..."
    python jobs/update_scores.py
    if [ $? -eq 0 ]; then
        echo "✅ NFL scores updated successfully"
    else
        echo "⚠️ NFL scores update failed, continuing anyway"
    fi

    echo "🔄 Running full score update to populate all weeks..."
    python jobs/update_scores.py
    if [ $? -eq 0 ]; then
        echo "✅ Full score update completed (includes all weeks + auto-eliminations)"
    else
        echo "⚠️ Score update failed, continuing anyway"
    fi

    echo "🔄 Backfilling historical data if needed..."
    python backfill_historical.py
    if [ $? -eq 0 ]; then
        echo "✅ Historical data backfilled successfully"
    else
        echo "⚠️ Historical backfill failed, continuing anyway"
    fi

    echo "📱 Mock data population complete"
fi

# Try to ingest real data from Google Sheets if OAuth is configured
echo "📊 Attempting real data ingestion from Google Sheets..."
python jobs/ingest_personal_sheets.py
if [ $? -eq 0 ]; then
    echo "✅ Real data ingested successfully from Google Sheets"
    echo "🧹 Real data replaces any mock data that was created"
else
    echo "⚠️ Real data ingestion failed, using mock data (if available)"
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

echo "🚀 All data processing complete, starting Streamlit..."

exec streamlit run app/main.py \
    --server.port=$PORT \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --server.enableCORS=false \
    --server.enableXsrfProtection=false