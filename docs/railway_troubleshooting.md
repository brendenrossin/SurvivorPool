# Railway Staging Setup Troubleshooting Guide

## Quick Setup Checklist

### Step 1: Create Staging Project in Railway
```bash
1. Go to railway.app dashboard
2. Click "New Project"
3. Name it "SurvivorPool-Staging"
4. Connect to GitHub repository
5. Select "staging" branch as source
```

### Step 2: Add PostgreSQL Database
```bash
1. In staging project → "Add Service"
2. Select "Database" → "PostgreSQL"
3. Wait for provisioning (2-3 minutes)
4. DATABASE_URL will auto-populate
```

### Step 3: Configure Environment Variables
```bash
# Required for main web service:
DATABASE_URL=(auto-set by Railway)
GOOGLE_SHEETS_SPREADSHEET_ID=1abc123...
GOOGLE_SERVICE_ACCOUNT_JSON_BASE64=eyJ0eXBlIjoi...
THE_ODDS_API_KEY=your_api_key_here
NFL_SEASON=2025
ENVIRONMENT=staging

# Optional (for debugging):
DEBUG=true
LOG_LEVEL=INFO
```

### Step 4: Get Webhook URLs
```bash
1. Go to staging project → Settings → Webhooks
2. Copy webhook URL
3. Add to GitHub Secrets as RAILWAY_STAGING_WEBHOOK
```

## Common Issues & Solutions

### Issue 1: Database Migration Fails
**Symptoms**: "column point_spread does not exist" errors
**Solution**:
```bash
# Check if migration script ran:
1. Railway logs → Look for "🎰 Applying odds integration migration"
2. If missing, manually run: python scripts/railway_migration.py
3. Verify columns exist in database console
```

### Issue 2: GitHub Action Not Triggering
**Symptoms**: No deployment after pushing to staging branch
**Solutions**:
```bash
# Check workflow file:
1. Ensure .github/workflows/deploy.yml exists
2. Verify branch name is "staging" (case-sensitive)
3. Check GitHub Actions tab for error messages

# Manual trigger:
1. GitHub → Actions → "Deploy to Railway"
2. "Run workflow" → Select staging
```

### Issue 3: Environment Variables Not Set
**Symptoms**: App crashes on startup, missing config errors
**Solution**:
```bash
# Verify all required variables:
1. Railway dashboard → staging project → Variables
2. Check each variable has correct value
3. No trailing spaces or quotes around values
4. BASE64 variables should be single line
```

### Issue 4: Cron Jobs Won't Start
**Symptoms**: Cron services fail to deploy
**Solution**:
```bash
# Each cron job needs separate Railway service:
1. Create new service in staging project
2. Connect to same GitHub repo
3. Set start command: python cron/[script_name].py
4. Set cron schedule in service settings
```

### Issue 5: Staging URL Not Working
**Symptoms**: 404 or timeout on staging URL
**Solutions**:
```bash
# Check deployment status:
1. Railway logs → Look for "Starting Streamlit"
2. Verify PORT environment variable is set
3. Check if database initialization completed
4. Look for any startup errors in logs
```

## Verification Commands

### Test Database Connection
```bash
# Run in Railway console or local with staging DATABASE_URL:
python -c "
import os
from sqlalchemy import create_engine, text
engine = create_engine(os.getenv('DATABASE_URL'))
with engine.connect() as conn:
    result = conn.execute(text('SELECT version()'))
    print('✅ Database connected:', result.fetchone()[0])
"
```

### Test Migration Status
```bash
# Check if odds columns exist:
python -c "
import os
from sqlalchemy import create_engine, text
engine = create_engine(os.getenv('DATABASE_URL'))
with engine.connect() as conn:
    result = conn.execute(text(\"\"\"
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'games'
        AND column_name IN ('point_spread', 'favorite_team')
    \"\"\"))
    columns = [row[0] for row in result]
    print('✅ Odds columns:', columns)
"
```

### Test App Health
```bash
# Check if app responds:
curl -I https://your-staging-app.up.railway.app
# Should return 200 OK
```

## Railway Service Configuration

### Main Web App
```toml
# railway.toml in repo root
[build]
builder = "nixpacks"

[deploy]
startCommand = "bash start.sh"
```

### Cron Services (separate Railway services)
```bash
# Service 1: Odds Update
Start Command: python cron/daily_odds_update.py
Cron: 0 13 * * *

# Service 2: Score Update
Start Command: python cron/score_update.py
Cron: 0 17,18,19,20,21,22,23,0,1,2 * * 0,1

# Service 3: Sheets Ingestion
Start Command: python cron/sheets_ingestion.py
Cron: 0 14 * * *
```

## Success Indicators

### ✅ Staging Setup Complete When:
- [ ] App loads at staging URL without errors
- [ ] Database has point_spread and favorite_team columns
- [ ] Live scores page displays (with or without betting lines)
- [ ] No console errors in browser developer tools
- [ ] GitHub Action shows successful deployment
- [ ] Railway logs show clean startup sequence

### ✅ Ready for Production When:
- [ ] All staging tests pass
- [ ] Cron jobs run manually without errors
- [ ] Mobile UI works on phone/tablet
- [ ] Database migration script tested
- [ ] API rate limits verified (The Odds API usage)

## Emergency Rollback

### If Staging Breaks:
```bash
1. Railway → Deployments → Rollback to previous version
2. Or redeploy from last known good commit
3. Check environment variables haven't changed
```

### If Need Fresh Database:
```bash
1. Delete PostgreSQL service in Railway
2. Add new PostgreSQL service
3. Let start.sh repopulate with mock data
```

This guide covers the most common setup issues. Next step is creating the migration test script!