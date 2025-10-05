# 🎓 Railway Deployment Lessons Learned

## ⚠️ CRITICAL: Read This Before Making Changes

This document contains hard-learned lessons from Railway deployment debugging. **Always check this before making deployment changes.**

---

## 🚀 Railway Deployment - DO's

### ✅ Working Architecture
- **USE Dockerfile approach** with `CMD ["./start.sh"]`
- **USE start.sh script** with proper Streamlit flags
- **KEEP railway.json minimal** - no custom startCommand
- **INCLUDE database initialization** in start.sh before Streamlit

### ✅ Required Streamlit Flags for Railway
```bash
streamlit run app/main.py \
    --server.port=$PORT \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --server.enableCORS=false \
    --server.enableXsrfProtection=false
```

### ✅ Testing Protocol
1. **ALWAYS test locally first** before pushing to Railway
2. **Test exact command syntax** in local shell scripts
3. **Verify environment variables** are properly expanded
4. **Check git history** for working commits when things break

---

## 🚫 Railway Deployment - DON'Ts

### ❌ NEVER Use These Patterns
- **DON'T use railway.json startCommand** - breaks critical Streamlit flags
- **DON'T use basic `streamlit run`** without Railway-specific flags
- **DON'T skip local testing** of deployment commands
- **DON'T deploy without checking working git history**

### ❌ Variable Expansion Issues
- **DON'T use `$PORT`** directly in railway.json (doesn't expand)
- **DON'T use `--server.port $PORT`** (space causes parsing issues)
- **DON'T assume Railway env vars** work same as local

---

## 🔍 Debugging Process

### When Getting 502 Errors:
1. **Check git history** - find last working commit
2. **Compare railway.json** - likely startCommand issue
3. **Verify Dockerfile CMD** - should use start.sh
4. **Check Streamlit flags** - Railway needs specific flags

### Error Patterns & Solutions:
```
Error: Invalid value for '--server.port': '$PORT' is not a valid integer
→ Solution: Use start.sh with proper variable handling

502 Application failed to respond
→ Solution: Revert to Dockerfile CMD approach

Container stopping after database init
→ Solution: Remove startCommand from railway.json
```

---

## 📁 File Structure - Working State

### railway.json (MINIMAL - Working)
```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "DOCKERFILE"
  },
  "deploy": {
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

### start.sh (COMPLETE - Working)
```bash
#!/bin/bash
# Database initialization
python init_db_railway.py

# Port handling
if [ -z "$PORT" ]; then
    PORT=8080
fi

# Streamlit with ALL required flags
exec streamlit run app/main.py \
    --server.port=$PORT \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --server.enableCORS=false \
    --server.enableXsrfProtection=false
```

---

## 🎯 Environment Variables (Railway Dashboard)

### Required Variables:
```
DATABASE_URL=postgresql://postgres:...@postgres.railway.internal:5432/railway
GOOGLE_OAUTH_TOKEN_JSON={"token": "...", "refresh_token": "..."}
GOOGLE_SHEETS_SPREADSHEET_ID=12dM-Ks5JLmjSQPWyVsigZIn6RguZx6m47yl-khamHFY
GOOGLE_SHEETS_PICKS_RANGE=Picks!A1:Z5000
NFL_SEASON=2025
SCORES_PROVIDER=espn
ENVIRONMENT=railway
```

---

## 🔄 Data Ingestion Strategy

### Working Approach:
1. **Database init** happens in start.sh
2. **Mock data population** if database empty
3. **OAuth ingestion** separate from startup (prevents timeouts)
4. **NFL scores** updated independently

### DON'T:
- **DON'T run data ingestion** in railway.json startCommand
- **DON'T block Streamlit startup** with slow operations
- **DON'T fail deployment** if OAuth/external APIs fail

---

## 🧪 Local Testing Commands

### Test Streamlit syntax:
```bash
PORT=8530 && streamlit run app/main.py --server.port=$PORT --server.address=0.0.0.0
```

### Test start.sh script:
```bash
export PORT=8531
export DATABASE_URL="sqlite:///debug_output/local_survivor.db"
./start.sh
```

---

## 📝 Commit Message Patterns

### Good commits:
- "REVERT to working Dockerfile approach"
- "Fix Streamlit command syntax - tested locally first"
- "Add database initialization to start.sh"

### Bad commits:
- "Try different Railway startup"
- "Fix deployment issues"
- "Update config"

---

## 🎭 Last Working State (Reference)

**Commit:** `d6acfb5` - "Fix mock data population with Railway-specific script"
**Key:** Used Dockerfile CMD with start.sh, no railway.json startCommand

When in doubt, compare current state to this working commit.

---

## 🔑 Google OAuth Token Revocation (CRITICAL)

### Problem
**Date:** 2025-10-05
**Symptom:** Sheets ingestion failing with `invalid_grant: Token has been expired or revoked`

**Root Cause:**
Google revokes OAuth refresh tokens if they're not used for extended periods (typically 6 months for production apps, shorter for apps in testing mode). Our access token expired and sat dormant without being refreshed, causing the refresh token to also be revoked.

### Solution

**Immediate Fix:**
1. Delete old `token.json`: `rm -f token.json`
2. Regenerate fresh credentials: `python scripts/testing/test_personal_sheets.py`
3. Browser will open for re-authentication
4. Encode for Railway: New token saved to `.credentials/.railway_oauth_token_FRESH.txt`
5. Update Railway environment variable `GOOGLE_OAUTH_TOKEN_JSON` with fresh base64 token

**Permanent Prevention:**
Created proactive token refresh system:

1. **Proactive Refresh Job** (`jobs/refresh_oauth_token.py`)
   - Checks and refreshes OAuth token before expiry
   - Saves refreshed tokens for Railway updates
   - Returns error codes for monitoring

2. **Integrated into Sheets Cron** (`cron/sheets_ingestion.py`)
   - Step 1: Refresh OAuth token
   - Step 2: Ingest sheets data
   - Ensures token is fresh before every ingestion

3. **Health Monitoring** (`jobs/monitor_oauth_health.py`)
   - Monitors `job_meta` table for OAuth failures
   - Alerts on authentication errors
   - Tracks time since last successful ingestion

### Key Learnings

- ⚠️ **OAuth tokens need regular refresh** - don't let them sit dormant
- 🔄 **Refresh before use** - always refresh token proactively before API calls
- 📊 **Monitor job_meta** - watch for OAuth error patterns in job messages
- 🚨 **Alert on failures** - catch token issues before they impact users
- 🔧 **Manual Railway updates required** - Railway env vars can't be updated from within the app (security feature)

### Testing Notes

Local testing requires setting env var:
```bash
export GOOGLE_OAUTH_TOKEN_JSON="<base64_token>"
python jobs/refresh_oauth_token.py
```

On Railway, env var is automatically available to cron jobs.

### Deployment Status
- ✅ Fresh OAuth token generated (2025-10-05)
- ✅ Railway production env var updated
- ✅ Proactive refresh added to sheets cron
- ✅ Health monitoring script created
- 📝 Documentation updated

---

*💡 Always update this document when learning new lessons or solving new deployment issues.*