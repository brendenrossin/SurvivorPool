# Railway Deployment Guide

## Overview
This guide covers deploying the Survivor Pool Dashboard to Railway, including all environment variables and the new odds integration.

## Prerequisites
- Railway account (railway.app)
- GitHub repository connected to Railway
- PostgreSQL database (Railway provides free tier)
- Google Sheets with survivor picks
- The Odds API account (optional, free tier)

## Environment Variables Setup

### Required Variables
Set these in Railway's Environment Variables section:

#### Database
```bash
DATABASE_URL=postgresql://username:password@host:port/database
```
*Railway auto-generates this if you add a PostgreSQL service*

#### Google Sheets Integration
```bash
GOOGLE_SHEETS_SPREADSHEET_ID=your_google_sheets_id
GOOGLE_SERVICE_ACCOUNT_JSON_BASE64=your_base64_encoded_json
```

#### Season Configuration
```bash
NFL_SEASON=2025
```

### Optional Variables

#### Betting Odds Integration (NEW)
```bash
THE_ODDS_API_KEY=your_odds_api_key
```
*Get from https://the-odds-api.com/ (500 free credits/month)*

#### Provider Configuration
```bash
SCORES_PROVIDER=espn
ODDS_PROVIDER=the_odds_api
```
*These are defaults and usually don't need to be set*

## Deployment Steps

### 1. Connect Repository
1. Go to Railway dashboard
2. Click "New Project"
3. Connect your GitHub repository
4. Railway will auto-detect Python and deploy

### 2. Add PostgreSQL Database
1. In your Railway project, click "New Service"
2. Select "Database" → "PostgreSQL"
3. Railway will create `DATABASE_URL` automatically

### 3. Configure Environment Variables
1. Go to your app service (not database)
2. Click "Variables" tab
3. Add all required variables listed above

### 4. Configure Startup
Railway uses `start.sh` which handles:
- Database initialization
- Data population (if needed)
- Score updates with odds
- Streamlit startup

### 5. Set Custom Domain (Optional)
1. Go to "Settings" tab
2. Add custom domain if desired
3. Railway provides free `*.railway.app` subdomain

## Database Initialization

### Automatic Setup
The `start.sh` script automatically:
1. Initializes database schema
2. Populates with mock data if empty
3. Tries to ingest real Google Sheets data
4. Updates scores and odds
5. Starts Streamlit dashboard

### Manual Database Setup
If needed, you can run commands manually:

```bash
# Connect to Railway PostgreSQL
railway login
railway link [your-project-id]
railway run psql $DATABASE_URL

# Initialize schema
\i db/migrations.sql
```

## Odds Integration Setup

### 1. Get The Odds API Key
1. Visit https://the-odds-api.com/
2. Sign up for free account (500 credits/month)
3. Get API key from dashboard

### 2. Add to Railway
1. Go to Railway Variables tab
2. Add variable:
   - **Name**: `THE_ODDS_API_KEY`
   - **Value**: Your API key

### 3. Verify Integration
Check Railway logs for:
```
🎰 Fetching NFL odds from The Odds API...
✅ Odds API: Fetched odds for X games
🎰 Added odds: MIA @ BUF - BUF -3.5
```

### 4. Monitor Usage
- Free tier: 500 credits/month
- Expected usage: ~64 credits/month (16 games × 4 weeks)
- Monitor in The Odds API dashboard

## Monitoring and Logs

### Railway Logs
Access via Railway dashboard or CLI:
```bash
railway logs
```

### Key Log Messages
```bash
# Successful startup
🚀 Starting Survivor Pool Dashboard...
✅ Database has sufficient data

# Odds integration
🎰 Fetching NFL odds from The Odds API...
✅ Odds API: Fetched odds for X games

# Data ingestion
📊 Attempting real data ingestion from Google Sheets...
✅ Real data ingested successfully

# Score updates
🏈 Fetching NFL games...
✅ NFL scores updated successfully
```

### Health Checks
The app automatically checks:
- Database connectivity
- Data availability
- API integrations

## Troubleshooting

### Common Issues

#### 1. Database Connection Errors
**Error**: `could not connect to server`
**Solution**:
- Check `DATABASE_URL` is set correctly
- Ensure PostgreSQL service is running
- Verify network connectivity

#### 2. Google Sheets Access Denied
**Error**: `403 Forbidden` or `Insufficient Permission`
**Solution**:
- Verify service account has sheet access
- Check `GOOGLE_SERVICE_ACCOUNT_JSON_BASE64` encoding
- Ensure sheet is shared with service account email

#### 3. Odds API Issues
**Error**: `⚠️ No Odds API key - skipping odds fetch`
**Solution**:
- Add `THE_ODDS_API_KEY` to Railway variables
- Verify API key is valid
- Check The Odds API dashboard for usage/errors

#### 4. Build Failures
**Error**: Build fails or times out
**Solution**:
- Check `requirements.txt` for conflicts
- Verify Python version compatibility
- Review Railway build logs

### Debug Commands

Access Railway shell:
```bash
railway shell
```

Run debug commands:
```bash
# Check environment variables
env | grep -E "(DATABASE|SHEETS|ODDS|NFL)"

# Test database connection
python -c "from api.database import SessionLocal; db = SessionLocal(); print('DB connected')"

# Test odds API
python -c "from api.odds_providers import get_odds_provider; print('Odds provider loaded')"

# Test Google Sheets
python -c "from api.sheets import GoogleSheetsClient; print('Sheets client loaded')"
```

## Performance and Scaling

### Resource Usage
- **Memory**: ~200-300MB typical
- **CPU**: Low, spikes during data updates
- **Storage**: Minimal (database only)
- **Network**: Moderate (API calls)

### Railway Limits (Free Tier)
- 500 hours/month execution time
- $5 resource limit
- 1GB memory limit
- Should be sufficient for survivor pool usage

### Optimization Tips
1. **Caching**: APIs use 30-minute cache
2. **Batch Updates**: Score updates run 1-2x per week
3. **Efficient Queries**: Database queries optimized
4. **Resource Monitoring**: Use Railway metrics

## Backup and Recovery

### Database Backups
Railway PostgreSQL includes automatic backups:
- Point-in-time recovery available
- Access via Railway dashboard

### Manual Backup
```bash
# Export data
railway run pg_dump $DATABASE_URL > backup.sql

# Restore data
railway run psql $DATABASE_URL < backup.sql
```

### Environment Variables Backup
Document all environment variables in a secure location:
```bash
# Example backup format
DATABASE_URL=postgresql://...
GOOGLE_SHEETS_SPREADSHEET_ID=1abc...
GOOGLE_SERVICE_ACCOUNT_JSON_BASE64=ewog...
NFL_SEASON=2025
THE_ODDS_API_KEY=abc123...
```

## Cost Management

### Free Tier Usage
- Railway: $0 (within limits)
- PostgreSQL: $0 (Railway free tier)
- The Odds API: $0 (500 credits/month)
- **Total**: $0/month for typical survivor pool

### Paid Upgrade Considerations
If you exceed free tiers:
- Railway: $5-20/month depending on usage
- The Odds API: $30/month for 20K credits (massive overkill)

### Cost Optimization
1. Monitor Railway resource usage
2. Track The Odds API credit consumption
3. Optimize data update frequency if needed
4. Consider caching strategies for popular queries