#!/bin/bash
echo "🚀 Starting app with PORT=$PORT"
echo "📝 Environment check:"
echo "  PORT: $PORT"
echo "  DATABASE_URL: ${DATABASE_URL:0:30}..."

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
from api.models import Player
try:
    db = SessionLocal()
    player_count = db.query(Player).count()
    db.close()
    if player_count == 0:
        print('🆕 Database is empty, will populate in background...')
        exit(1)
    else:
        print(f'✅ Database has {player_count} players, skipping population')
        exit(0)
except Exception as e:
    print(f'⚠️ Database check failed: {e}, starting app anyway...')
    exit(0)
"

if [ $? -eq 1 ]; then
    echo "🔄 Starting background data population..."
    nohup python populate_data.py > logs/populate.log 2>&1 &
    echo "📱 Data population running in background, starting Streamlit..."
fi

exec streamlit run app/main.py \
    --server.port=$PORT \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --server.enableCORS=false \
    --server.enableXsrfProtection=false