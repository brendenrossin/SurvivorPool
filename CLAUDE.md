# CLAUDE.md - Project Context & Conventions

## 🎯 Project Overview

**Survivor Pool Dashboard** - A lightweight, cost-effective NFL elimination pool tracker
- **Tech Stack**: Streamlit + PostgreSQL + Railway hosting
- **Architecture**: MVP with cron jobs for data ingestion
- **Status**: 95% MVP complete and fully functional
- **URL**: https://nfl-survivor-2025.up.railway.app/

## 🏗️ Architecture & Design Patterns

### Core Principles
- **Lightweight & cheap**: Designed for free-tier hosting
- **Database-first**: All data flows through PostgreSQL, no real-time APIs in UI
- **Mobile-optimized**: Streamlit with custom mobile chart configurations
- **Cached performance**: Streamlit caching for all expensive operations

### Key Components
```
app/main.py              # Main Streamlit dashboard
app/dashboard_data.py    # Cached data fetching (st.cache_data)
app/live_scores.py       # Live game status widgets
jobs/                    # Background ingestion workers
api/                     # Database models & connections
```

## 📊 Data Flow & Caching Strategy

### Caching Patterns (CRITICAL)
Always use Streamlit caching for database operations:

```python
@st.cache_data(ttl=60)  # 60s for live data
def get_summary_data(season: int) -> Dict:
    SessionFactory = get_db_session()
    db = SessionFactory()
    # ... database operations

@st.cache_resource
def get_db_session():
    return SessionLocal
```

### Database Session Pattern
Always use try/finally for session cleanup:
```python
try:
    db = SessionLocal()
    try:
        # database operations
    finally:
        try:
            db.close()
        except:
            pass
except Exception as e:
    # handle error
```

## 🎨 UI/UX Conventions

### Color Mapping
Use centralized team colors from `load_team_data()`:
```python
def get_team_color_map():
    team_data = load_team_data()
    return {team: data.get("color", "#666666") for team, data in team_data["teams"].items()}
```

### Mobile Optimization
- Limit chart annotations (top-3 teams only)
- Use `render_mobile_chart()` for all Plotly figures
- Status chips: 🔴 **LIVE** / ✅ **FINAL** / 🕐 **PRE**

### Performance Guidelines
- Cache all database reads with appropriate TTL
- Use expandable sections for long lists
- Optimize chart annotations for mobile

## 🚀 Railway Deployment (CRITICAL LESSONS)

### ✅ Working Deployment Pattern
```dockerfile
# Dockerfile with start.sh
CMD ["./start.sh"]
```

```bash
# start.sh
#!/bin/bash
python init_db_railway.py

if [ -z "$PORT" ]; then
    PORT=8080
fi

exec streamlit run app/main.py \
    --server.port=$PORT \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --server.enableCORS=false \
    --server.enableXsrfProtection=false
```

```json
// railway.json (MINIMAL - No startCommand!)
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {"builder": "DOCKERFILE"},
  "deploy": {
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

### ❌ Never Do This
- ❌ Don't use `railway.json` startCommand (breaks port expansion)
- ❌ Don't use basic `streamlit run` without Railway flags
- ❌ Don't deploy without testing locally first
- ❌ Don't use `$PORT` directly in railway.json (doesn't expand)

## 🗃️ Database Patterns

### Models & Relationships
```
players → picks → pick_results ← games
```

### Key Tables
- `players`: Unique display names
- `picks`: Player picks per week/season (with team_abbr)
- `pick_results`: Survival status linked to games
- `games`: NFL schedule/scores from ESPN
- `job_meta`: Track last update timestamps

### Survival Logic
- Player eliminated when any `pick_results.survived = false`
- Remaining = players with no `survived = false` records

## 🔧 Development Workflows

### Local Development
```bash
# Setup
source .venv/bin/activate
pip install -r requirements.txt

# Database operations
python -c "from api.database import init_db; init_db()"
python jobs/backfill_weeks.py --weeks 1 2
python jobs/ingest_sheet.py
python jobs/update_scores.py

# Run dashboard
streamlit run app/main.py
```

### Testing Deployment Commands Locally
```bash
# Test start.sh locally
export PORT=8531
export DATABASE_URL="sqlite:///debug_output/local_survivor.db"
./start.sh

# Test Streamlit syntax
PORT=8530 && streamlit run app/main.py --server.port=$PORT --server.address=0.0.0.0
```

## 📈 Data Sources & APIs

### Google Sheets Integration
- Service account with read-only access
- Automatic parsing of Name + Week columns
- Team abbreviation validation against `load_team_data()`

### NFL Data (ESPN)
- Free ESPN API for schedules/scores
- No API key required
- Fallback providers available (SportRadar, etc.)

### Cron Job Schedule
```
Sheet Ingestion: 07:00 PT daily + 09:30 PT Sundays
Score Updates: Hourly Sun 10-21 PT + Mon/Thu 21 PT
```

## 🐛 Common Issues & Solutions

### Performance Issues
```python
# Problem: Slow page loads
# Solution: Add caching to expensive functions
@st.cache_data(ttl=60)
def expensive_function():
    pass
```

### Database Connection Leaks
```python
# Problem: Too many connections
# Solution: Always use try/finally cleanup
try:
    db = SessionLocal()
    # operations
finally:
    try: db.close()
    except: pass
```

### Railway 502 Errors
```bash
# Problem: App won't start on Railway
# Solution: Revert to Dockerfile CMD approach, remove railway.json startCommand
git log --oneline  # Find last working commit
```

## 🎮 Feature Development Guidelines

### Adding New Widgets
1. Create in separate file (e.g., `app/new_widget.py`)
2. Import and call from `main.py`
3. Use cached data functions
4. Add proper database session cleanup
5. Follow mobile-first design

### Database Schema Changes
1. Update `api/models.py`
2. Create migration script in `db/`
3. Test locally before deploying
4. Update seed data if needed

### New API Integrations
1. Add provider interface in `api/`
2. Implement with fallbacks
3. Add configuration via environment variables
4. Test with mock data first

## 📝 Code Style & Conventions

### Imports
```python
import streamlit as st
import pandas as pd
from datetime import datetime
# ... standard library first, then third-party, then local
```

### Error Handling
```python
try:
    # risky operation
    pass
except Exception as e:
    st.warning(f"⚠️ Expected error: {e}")
    # Always provide user-friendly fallback
```

### Documentation
- Add docstrings to all functions
- Include type hints where helpful
- Comment deployment-critical patterns

## 🔍 Debugging & Monitoring

### Local Debugging
```python
# Add temporary debug output
st.write(f"DEBUG: {variable}")  # Remove before commit

# Database debugging
print(f"Query result: {result}")
```

### Production Monitoring
- Check Railway logs for startup issues
- Monitor `job_meta` table for update failures
- Use `last_updates` timestamps in footer
- **OAuth Health Check**: `python jobs/monitor_oauth_health.py`

### OAuth Token Maintenance (AUTOMATIC ✨)

**How It Works:**
Google OAuth uses TWO tokens:
- **Access Token**: Short-lived (~1 hour) - used for API calls
- **Refresh Token**: Long-lived (6+ months) - used to get new access tokens

Our system **automatically refreshes** access tokens using the refresh token:
- `api/oauth_manager.py` detects expired access tokens
- Automatically requests new access token using refresh_token
- **No manual intervention needed!** 🎉

**One-Time Setup (only when refresh token is revoked):**
```bash
# 1. Delete old token
rm -f token.json

# 2. Generate fresh credentials (opens browser for Google OAuth)
python scripts/testing/test_personal_sheets.py

# 3. Token is automatically base64-encoded and saved to:
#    .credentials/.railway_oauth_token_FRESH.txt

# 4. Update Railway environment variable ONCE
# Railway Dashboard → Service → Variables → GOOGLE_OAUTH_TOKEN_JSON
# Copy token from .railway_oauth_token_FRESH.txt
```

**After setup:** The system will automatically refresh for 6+ months!

**Monitoring OAuth Health:**
```bash
# Check for OAuth failures
python jobs/monitor_oauth_health.py

# Look for these alerts:
# - "CRITICAL: OAuth authentication failure detected"
# - "WARNING: Sheets ingestion hasn't run in 48+ hours"
# - "CRITICAL: No successful ingestion in 72+ hours"
```

**OAuth Failure Response (only if refresh token is revoked):**
1. Check Railway logs for `invalid_grant` with "Token has been expired or revoked"
2. If refresh_token is revoked, regenerate with test_personal_sheets.py
3. Update Railway GOOGLE_OAUTH_TOKEN_JSON variable
4. System will auto-refresh for another 6+ months

## 📚 Reference Commands

### Useful Database Queries
```sql
-- Check job status
SELECT * FROM job_meta ORDER BY last_run_at DESC;

-- Check elimination status
SELECT COUNT(*) FROM players WHERE player_id NOT IN (
    SELECT DISTINCT p.player_id FROM picks p
    JOIN pick_results pr ON p.pick_id = pr.pick_id
    WHERE pr.survived = false
);
```

### Git Workflow
```bash
# Always test locally before pushing
git add .
git commit -m "descriptive message"
git push origin staging  # Auto-deploys to Railway
```

## 🎯 MVP vs Future Features

### ✅ Current MVP Features
- Google Sheets integration
- Live NFL scores
- Interactive dashboard
- Mobile optimization
- Caching & performance optimization

### 🔮 V1.5 Ideas (from checklist)
- Odds integration & Chaos Meter
- Future Power Gauge
- Enhanced graveyard features
- Email notifications
- Advanced analytics

## 🚨 Critical Reminders

1. **Always cache database operations** with appropriate TTL
2. **Never commit secrets** - use environment variables
3. **Test Railway deployment locally** before pushing
4. **Follow mobile-first design** for all UI components
5. **Use proper database session cleanup** everywhere
6. **Check LESSONS_LEARNED.md** for deployment gotchas

## 📞 Support & Resources

- **Railway Docs**: https://docs.railway.app/
- **Streamlit Docs**: https://docs.streamlit.io/
- **Project Status**: Track in `docs/app_instructions.md`
- **Known Issues**: See `LESSONS_LEARNED.md`

---

*Last Updated: 2025-09-21*
*This file should be updated whenever significant patterns or lessons are discovered.*