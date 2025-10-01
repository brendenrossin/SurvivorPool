#!/bin/bash
# Dev environment startup script with multi-league support
echo "🚀 Starting DEV environment with PORT=$PORT"
echo "📝 Environment: DEV"
echo "  PORT: $PORT"
echo "  DATABASE_URL: ${DATABASE_URL:0:30}..."

# Initialize database schema (creates tables if they don't exist)
echo "🗄️ Initializing database schema..."
python init_db_railway.py

# Run multi-league migration
echo "🏗️ Running multi-league migration..."
python scripts/migrate_to_multi_league.py
if [ $? -eq 0 ]; then
    echo "✅ Multi-league migration completed successfully"
else
    echo "⚠️ Multi-league migration failed or already applied"
fi

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

# Check if database needs initial data population
echo "📊 Checking database state..."
python -c "
from api.database import SessionLocal
from api.models import Player, Pick, League
try:
    db = SessionLocal()
    league_count = db.query(League).count()
    player_count = db.query(Player).count()
    pick_count = db.query(Pick).count()
    db.close()

    print(f'📊 Current state: {league_count} leagues, {player_count} players, {pick_count} picks')

    if player_count == 0:
        print('🆕 Fresh database detected, will populate with test data...')
        exit(1)
    else:
        print(f'✅ Database has data ({player_count} players, {pick_count} picks)')
        exit(0)
except Exception as e:
    print(f'⚠️ Database check failed: {e}')
    exit(1)
"

if [ $? -eq 1 ]; then
    echo "🔄 Populating database with mock data for league_id=1..."

    # Check if railway_populate_mock.py exists
    if [ -f "railway_populate_mock.py" ]; then
        python railway_populate_mock.py
    else
        echo "⚠️ railway_populate_mock.py not found, skipping mock data"
    fi

    echo "🏈 Fetching NFL games..."
    python jobs/update_scores.py
    if [ $? -eq 0 ]; then
        echo "✅ NFL scores updated successfully"
    else
        echo "⚠️ NFL scores update failed, continuing anyway"
    fi
fi

echo "🎯 Starting Streamlit on port $PORT"
echo "🚀 Dev environment ready!"

exec streamlit run app/main.py \
    --server.port=$PORT \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --server.enableCORS=false \
    --server.enableXsrfProtection=false
