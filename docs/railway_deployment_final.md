# Railway Deployment Guide - Final Instructions

## Summary
✅ **Database Migration**: Auto-applies on startup
✅ **Odds Integration**: Fully functional with corrected logic
✅ **Cron Jobs**: Ready for Railway configuration
✅ **Local Testing**: All components verified

## 1. Deploy Main Application

The main web service will deploy automatically with the current push.

**What happens on startup:**
1. Database initialization
2. **Auto-migration** - Adds `point_spread` and `favorite_team` columns
3. Mock data population (if needed)
4. Real data ingestion from Google Sheets
5. Streamlit dashboard startup

## 2. Set Up Railway Cron Jobs

Railway requires **separate services** for each cron job. You'll need to create 3 additional services:

### Service 1: Daily Odds Update
1. **Create New Service** in Railway dashboard
2. **Connect** to the same GitHub repository
3. **Settings** → **Source** → Use `cron/railway-odds.toml` as config
4. **Or manually set:**
   - **Start Command**: `python cron/daily_odds_update.py`
   - **Cron Schedule**: `0 13 * * *` (8:00 AM EST daily)

### Service 2: Score Updates
1. **Create New Service** in Railway dashboard
2. **Connect** to the same GitHub repository
3. **Settings** → **Source** → Use `cron/railway-scores.toml` as config
4. **Or manually set:**
   - **Start Command**: `python cron/score_update.py`
   - **Cron Schedule**: `0 17,18,19,20,21,22,23,0,1,2 * * 0,1` (Sunday hourly + Monday night)

### Service 3: Sheets Ingestion
1. **Create New Service** in Railway dashboard
2. **Connect** to the same GitHub repository
3. **Settings** → **Source** → Use `cron/railway-sheets.toml` as config
4. **Or manually set:**
   - **Start Command**: `python cron/sheets_ingestion.py`
   - **Cron Schedule**: `0 14 * * *` (9:00 AM EST daily)

## 3. Environment Variables

**Each service** (including cron jobs) needs these environment variables:

### Required for All Services:
- `DATABASE_URL` (auto-set by Railway)
- `GOOGLE_SHEETS_SPREADSHEET_ID`
- `GOOGLE_SERVICE_ACCOUNT_JSON_BASE64`
- `NFL_SEASON=2025`

### Required for Odds Service:
- `THE_ODDS_API_KEY` (your API key)

## 4. Verify Deployment

### Check Main Application:
1. Visit your Railway app URL
2. Verify Live Scores show betting lines: "vs (Team -X.X)"
3. Check that Big Balls section loads (may show 🐕 for underdogs)

### Check Cron Jobs:
1. Go to each cron service → **Logs**
2. Verify they start and exit cleanly
3. Check database for updated odds/scores after runs

## 5. API Usage Monitoring

- **The Odds API**: Monitor usage at [https://the-odds-api.com/dashboard](https://the-odds-api.com/)
- **Expected Usage**: ~30 calls/month (well within 500 free limit)

## 6. Troubleshooting

### Database Column Errors:
- Fixed automatically by migration script in start.sh
- Should not occur with latest deployment

### Cron Jobs Not Running:
- Verify each service has correct environment variables
- Check logs for exit codes (should be 0 for success)
- Ensure cron schedule format is correct

### Betting Lines Not Showing:
- Verify `THE_ODDS_API_KEY` is set
- Check main app logs for odds integration messages
- Ensure database migration completed successfully

## 7. Current Status

- **Local Testing**: ✅ Complete
- **Database Migration**: ✅ Automated
- **Odds Logic**: ✅ Fixed (GB -8.5, not CLE -8.5)
- **Cron Scripts**: ✅ Working
- **Ready for Deployment**: ✅ Yes

The application is fully tested and ready for Railway deployment with native cron scheduling!