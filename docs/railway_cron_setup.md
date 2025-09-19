# Railway Cron Jobs Setup Guide

This guide explains how to set up automated cron jobs for your SurvivorPool Railway deployment.

## 🎯 What We Need to Schedule

1. **Sheets Ingestion** (`cron_ingest_sheets.py`) - Every hour to get fresh picks
2. **Score Updates** (`cron_update_scores.py`) - Every 30 minutes during game times
3. **Weekly Backfill** (`cron_backfill.py`) - Daily to ensure data completeness

## 📋 Railway Dashboard Setup Steps

### 1. Create Additional Services

In your Railway project dashboard:

1. **Go to your project** → `nfl-survivor-2025`
2. **Click "Add Service"** → **"Empty Service"**
3. **Create 5 new services** with these names:
   - `sheets-cron`
   - `scores-cron-sunday`
   - `scores-cron-monday`
   - `scores-cron-thursday`
   - `backfill-cron` (optional - can remove after one-time use)

### 2. Configure Each Cron Service

For each cron service, you need to:

#### A. Connect to GitHub Repository
1. **Service Settings** → **Source** → **Connect Repository**
2. **Select:** `brendenrossin/SurvivorPool`
3. **Branch:** `main`

#### B. Set Environment Variables
1. **Service Settings** → **Variables**
2. **Copy all variables from your main web service:**
   - `DATABASE_URL` (Reference from web service)
   - `GOOGLE_SHEETS_SPREADSHEET_ID`
   - `GOOGLE_SERVICE_ACCOUNT_JSON_BASE64`
   - `NFL_SEASON=2025`
   - `SCORES_PROVIDER=espn`
   - `ENVIRONMENT=production`

#### C. Configure Cron Schedule and Start Command

**For `sheets-cron` service:**
- **Settings** → **Cron Schedule:** `5 * * * *` (every hour at 5 past)
- **Settings** → **Deploy** → **Start Command:** `python cron_ingest_sheets.py`

**For `scores-cron` service:**
Create **3 separate cron services** for different game schedules:

**`scores-cron-sunday`:**
- **Settings** → **Cron Schedule:** `*/15 * * * 0` (every 15 minutes on Sundays)
- **Settings** → **Deploy** → **Start Command:** `python cron_update_scores.py`

**`scores-cron-monday`:**
- **Settings** → **Cron Schedule:** `*/15 1-5 * * 1` (every 15 min, 1-5 AM UTC = 5:30-9:30 PM PST Monday)
- **Settings** → **Deploy** → **Start Command:** `python cron_update_scores.py`

**`scores-cron-thursday`:**
- **Settings** → **Cron Schedule:** `*/15 1-5 * * 4` (every 15 min, 1-5 AM UTC = 5:30-9:30 PM PST Thursday)
- **Settings** → **Deploy** → **Start Command:** `python cron_update_scores.py`

**For `backfill-cron` service:**
- **Settings** → **Cron Schedule:** `0 6 * * *` (daily at 6 AM UTC = 2 AM ET)
- **Settings** → **Deploy** → **Start Command:** `python cron_backfill.py`

### 3. Deploy All Services

After configuring each service:
1. **Click "Deploy"** on each cron service
2. **Monitor logs** to ensure they're working correctly

## 📊 Cron Schedule Explanation

| Service | Schedule | Frequency | Reasoning |
|---------|----------|-----------|-----------|
| **Sheets** | `5 * * * *` | Every hour at :05 | Keep picks data fresh without overwhelming the API |
| **Scores** | `*/15 * * * 0` | Every 15 min on Sundays | Live score updates ONLY during game days (rate limit protection) |
| **Backfill** | `0 6 * * *` | Daily 6 AM UTC | Clean up any missed data overnight |

## 🔧 Alternative: Manual Cron Commands

If you prefer to test manually first, you can run these commands in your Railway web service console:

```bash
# Test sheets ingestion
python cron_ingest_sheets.py

# Test score updates
python cron_update_scores.py

# Test backfill
python cron_backfill.py
```

## ⚠️ Important Notes

1. **UTC Timezone:** All cron jobs run in UTC. NFL games are typically:
   - Sunday 1 PM ET = 18:00 UTC
   - Sunday 8:30 PM ET = 01:30 UTC Monday

2. **Exit Behavior:** Cron scripts must exit when complete (✅ our scripts do this)

3. **Resource Sharing:** All services share the same PostgreSQL database

4. **Monitoring:** Check Railway logs to ensure cron jobs are executing successfully

## 🎯 Expected Behavior

Once set up, you should see:
- **Hourly:** Fresh picks data ingested from Google Sheets
- **Every 30 min:** Live NFL scores and game statuses updated
- **Daily:** Historical data backfilled and validated
- **Real-time dashboard:** Always showing current survivor pool status!

Your survivor pool will now update automatically! 🏈🎉