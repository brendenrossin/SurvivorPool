# Multi-League Development Guide

This document outlines the development workflow for adding multi-league support to the Survivor Pool application.

## 🎯 **Architecture Overview**

### **Database Schema**

```
leagues (new)
  ├── league_id (PK)
  ├── league_name
  ├── league_slug (unique, URL-safe)
  ├── pick_source ('google_sheets' or 'in_app')
  ├── google_sheet_id (nullable)
  ├── season
  ├── commissioner_email
  ├── invite_code (unique)
  └── settings (JSONB)

players
  ├── player_id (PK)
  ├── display_name
  └── league_id (FK to leagues) ← ADDED

picks
  ├── pick_id (PK)
  ├── player_id (FK)
  ├── league_id (FK to leagues) ← ADDED
  ├── season
  ├── week
  └── team_abbr

users (new)
  ├── user_id (PK)
  ├── email (unique)
  ├── password_hash
  └── auth_provider

user_players (new junction table)
  ├── user_id (FK to users)
  └── player_id (FK to players)

league_commissioners (new)
  ├── league_id (FK to leagues)
  ├── user_id (FK to users)
  └── role ('commissioner' or 'admin')
```

### **Key Changes**

1. **Backward Compatible**: Existing single-league data becomes "League 1"
2. **League Isolation**: All queries filter by `league_id`
3. **Hybrid Pick Sources**: Support both Google Sheets AND in-app picks
4. **Multi-User Support**: One user can manage players across multiple leagues

---

## 🚀 **Development Environment Setup**

### **Step 1: Add Dev Environment to Existing Railway Project**

**IMPORTANT:** You should add a dev environment to your **EXISTING Railway project**, NOT create a new project. This keeps all environments (production, staging, dev) in one place.

#### **1.1: Navigate to Your Existing Project**

1. Go to Railway dashboard: https://railway.app
2. Click on your **existing SurvivorPool project** (the one with production and staging)
3. You should see your current services (e.g., "postgres", "web", etc.)

#### **1.2: Add a New PostgreSQL Database for Dev**

1. Click **"+ New"** button in the top right
2. Select **"Database"** → **"Add PostgreSQL"**
3. The database will be created automatically
4. **Rename the service** (click on the service name):
   - Change from "Postgres" to **"postgres-dev"**
   - This makes it clear it's the dev database

#### **1.3: Add a New Web Service for Dev**

1. Click **"+ New"** button again
2. Select **"GitHub Repo"**
3. Choose your **SurvivorPool repository**
4. Railway will create a new service

#### **1.4: Configure the Dev Web Service**

1. Click on the newly created web service
2. Go to **"Settings"** tab
3. Configure the following:

   **Service Name:**
   - Change to: **"web-dev"** (so you can distinguish it from production)

   **Source:**
   - Click "Configure" under Source
   - **Branch**: Select `feature/multi-league`
   - **Root Directory**: `/` (leave as default)
   - Click "Save"

   **Build & Deploy:**
   - **Start Command**: `./start.sh` (should be auto-detected from your code)
   - **Build Command**: (leave empty, we use Dockerfile)

   **Domains:**
   - Railway will auto-generate a domain like `web-dev-production-abc123.up.railway.app`
   - You can customize this later if you want

#### **1.5: Link Dev Web Service to Dev Database**

1. While still in the **web-dev service**, go to the **"Variables"** tab
2. Click **"+ New Variable"**
3. Add the following variables one by one:

**Critical Variables:**

| Variable Name | Value | Notes |
|--------------|-------|-------|
| `DATABASE_URL` | `${{postgres-dev.DATABASE_URL}}` | ⚠️ **CRITICAL**: Links to dev DB, not production! |
| `NFL_SEASON` | `2025` | Current season |
| `IS_DEV_ENV` | `true` | Flag to enable dev features |
| `PORT` | `8080` | Railway sets this automatically, but good to have |

**Optional (for Google Sheets testing):**

| Variable Name | Value | Notes |
|--------------|-------|-------|
| `GOOGLE_SHEETS_SPREADSHEET_ID` | `<your-test-sheet-id>` | Use a TEST sheet, not production! |
| `GOOGLE_SERVICE_ACCOUNT_JSON_BASE64` | `<base64-encoded-creds>` | Same as production (read-only) |
| `COMMISSIONER_EMAIL` | `your-email@example.com` | For default league creation |

**How to Set DATABASE_URL:**

The syntax `${{postgres-dev.DATABASE_URL}}` is Railway's way of referencing another service's variable. Here's what it does:

- `postgres-dev` = the name of your dev database service
- `.DATABASE_URL` = the connection string variable from that service
- Railway automatically replaces this with the actual database URL at runtime

**Verify it's correct:**
- After saving, click on `DATABASE_URL` to expand it
- It should show a PostgreSQL connection string starting with `postgresql://`
- Make sure it's different from your production database URL!

#### **1.6: Deploy the Dev Environment**

1. Go to the **"Deployments"** tab of your web-dev service
2. Click **"Deploy"** (or wait for auto-deploy if enabled)
3. Watch the build logs - you should see:
   - `🚀 Starting app with PORT=8080`
   - `🗄️ Initializing database...`
   - Database migration messages
   - `🎯 Starting Streamlit on port 8080`

#### **1.7: Verify Dev Environment is Separate**

**Check that dev is isolated from production:**

1. **Dev database should be empty** (no players/picks yet)
2. **Production database is untouched** (still has 127 survivors)
3. **Dev URL is different** from production URL

**Your Railway project should now look like this:**

```
SurvivorPool Project
├── postgres (production database)
│   └── Contains: 252 players, 127 survivors, all production data
│
├── postgres-dev (NEW - dev database)
│   └── Contains: Empty (will be populated after migration)
│
├── web (production service)
│   ├── Branch: main
│   ├── URL: nfl-survivor-2025.up.railway.app
│   └── Database: postgres
│
├── web-staging (staging service)
│   ├── Branch: staging
│   ├── URL: staging-xyz123.up.railway.app
│   └── Database: postgres (shared with production)
│
└── web-dev (NEW - dev service)
    ├── Branch: feature/multi-league
    ├── URL: web-dev-abc456.up.railway.app
    └── Database: postgres-dev (separate!)
```

**Why This Setup?**

✅ **All environments in one project** = Easy to manage and compare
✅ **Separate dev database** = Can't accidentally corrupt production data
✅ **Automatic deployments** = Push to branch, Railway auto-deploys
✅ **Easy rollback** = If dev breaks, production is unaffected
✅ **Cost-effective** = Single Railway subscription covers all environments

### **Step 2: Run Migration on Dev Database**

Now that your dev environment is set up, you need to run the database migration to add multi-league support.

#### **Method 1: Run Migration via Railway CLI (Easiest)**

1. **Install Railway CLI** (if you haven't already):
   ```bash
   # Mac/Linux
   brew install railway

   # Or via npm
   npm install -g @railway/cli
   ```

2. **Login to Railway:**
   ```bash
   railway login
   ```

3. **Link to your dev service:**
   ```bash
   # Navigate to your local project directory
   cd /path/to/SurvivorPool

   # Link to Railway
   railway link
   # Select: SurvivorPool project → web-dev service
   ```

4. **Run the migration:**
   ```bash
   railway run python scripts/migrate_to_multi_league.py
   ```

   You should see output like:
   ```
   ======================================================================
   MULTI-LEAGUE MIGRATION - Adding league support to database
   ======================================================================

   📄 Reading migration from: db/migrations/001_add_multi_league_support.sql
   🔄 Executing migration...
   📝 Updating default league with environment values...
   ✅ Migration executed successfully!

   🔍 Verifying migration...
     ✓ Leagues table created: 1 league(s)
     ✓ Players migrated: 0 player(s) with league_id
     ✓ Picks migrated: 0 pick(s) with league_id
     ✓ Users table created: 0 user(s)

   ======================================================================
   ✨ MIGRATION COMPLETE!
   ======================================================================
   ```

#### **Method 2: Run Migration Locally (Alternative)**

If Railway CLI doesn't work, you can run the migration from your local machine:

1. **Get the dev database URL from Railway:**
   - Go to Railway dashboard
   - Click on **postgres-dev** service
   - Go to **"Variables"** tab
   - Copy the `DATABASE_URL` value (starts with `postgresql://`)

2. **Run migration locally pointing to dev database:**
   ```bash
   # Set environment variable to dev database
   export DATABASE_URL="postgresql://postgres:abc123@containers-us-west-xyz.railway.app:1234/railway"

   # Run migration
   python scripts/migrate_to_multi_league.py
   ```

3. **Verify migration succeeded:**
   ```bash
   # Check that tables were created
   psql $DATABASE_URL -c "SELECT * FROM leagues;"

   # Should show 1 league (the default league)
   ```

#### **Method 3: Via Railway Web Interface (Last Resort)**

If neither of the above work:

1. Go to Railway dashboard → **web-dev** service
2. Go to **"Deployments"** tab
3. Click on the most recent deployment
4. Click **"View Logs"**
5. The migration should run automatically on startup (if configured in `start.sh`)

**⚠️ Important Notes:**

- The migration is **idempotent** - safe to run multiple times
- The dev database starts empty, so migration will create tables from scratch
- Default league (ID=1) will be created automatically
- No production data will be affected (completely separate database)

### **Step 3: Verify Migration and Test Dev Environment**

After the migration completes, verify everything is set up correctly:

#### **3.1: Check Dev Database Has League Tables**

```bash
# Connect to dev database (using DATABASE_URL from Railway)
psql $DATABASE_URL

# List all tables
\dt

# You should see:
# - leagues
# - users
# - user_players
# - league_commissioners
# - players (with league_id column)
# - picks (with league_id column)
# - games
# - pick_results
# - job_meta

# Check default league was created
SELECT * FROM leagues;

# Should show 1 row with league_id=1
```

#### **3.2: Test the Dev Dashboard**

1. Open your dev environment URL (e.g., `https://web-dev-abc456.up.railway.app`)
2. The dashboard should load (but with no data since it's a fresh database)
3. You should see:
   - "0 Remaining Survivors"
   - "0 Total Players"
   - Empty charts

**This is EXPECTED!** The dev database is empty - we'll populate it next.

#### **3.3: Populate Dev Database with Test Data (Optional)**

If you want to test with real data, you can:

**Option A: Copy production data to dev (for testing)**

```bash
# Dump production data
pg_dump $PRODUCTION_DATABASE_URL > production_backup.sql

# Restore to dev (CAUTION: This will overwrite dev data)
psql $DEV_DATABASE_URL < production_backup.sql
```

**Option B: Use mock data (safer for testing)**

```bash
# If you have a mock data script
railway run python scripts/railway_populate_mock.py
```

**Option C: Manually create test data**

```bash
railway run python -c "
from api.database import SessionLocal
from api.models import League, Player, Pick

db = SessionLocal()

# Verify default league exists
league = db.query(League).filter(League.league_id == 1).first()
print(f'Default league: {league.league_name}')

# Create a test player
player = Player(display_name='Test Player', league_id=1)
db.add(player)
db.commit()

print(f'Created test player: {player.display_name}')
db.close()
"
```

---

## 🛠️ **Local Development Workflow**

### **Option A: Test Against Dev Railway Database**

```bash
# Set environment variable to point to dev database
export DATABASE_URL="postgresql://user:pass@dev-db-host:port/railway"

# Run migration
python scripts/migrate_to_multi_league.py

# Test dashboard
streamlit run app/main.py
```

### **Option B: Test Against Local PostgreSQL**

```bash
# Install PostgreSQL locally
brew install postgresql
brew services start postgresql

# Create local database
createdb survivor_pool_dev

# Set environment variable
export DATABASE_URL="postgresql://localhost/survivor_pool_dev"

# Run migration
python scripts/migrate_to_multi_league.py

# Test dashboard
streamlit run app/main.py
```

---

## 📝 **Migration Details**

### **What the Migration Does**

1. **Creates new tables**: `leagues`, `users`, `user_players`, `league_commissioners`
2. **Adds `league_id`** to `players` and `picks` tables
3. **Creates default league** (League ID = 1) for existing data
4. **Migrates all existing players/picks** to League 1
5. **Makes `league_id` NOT NULL** after migration

### **Running the Migration**

```bash
# Run migration
python scripts/migrate_to_multi_league.py

# Verify migration
python scripts/migrate_to_multi_league.py --verify

# Rollback (for testing only - DELETES LEAGUE DATA!)
python scripts/migrate_to_multi_league.py --rollback
```

### **Rollback Warning**

⚠️ **Rollback will DELETE all league data!** Only use for testing on dev database.

---

## 🧪 **Testing Checklist**

### **Phase 1: Backward Compatibility (CRITICAL)**

- [ ] Existing dashboard loads without errors
- [ ] All 127 survivors still show correctly
- [ ] Pick history displays correctly
- [ ] Graveyard shows eliminated players
- [ ] Team picks breakdown works
- [ ] Live scores widget functions

### **Phase 2: Multi-League Queries**

- [ ] Queries filter by `league_id` correctly
- [ ] Creating a second league doesn't affect League 1 data
- [ ] Deleting a league cascades to players/picks
- [ ] League isolation prevents cross-league data leaks

### **Phase 3: In-App Picks (Future)**

- [ ] User can create account
- [ ] User can join league via invite code
- [ ] User can submit picks via form
- [ ] Picks validate (no repeat teams, no started games)
- [ ] Pick edits work before game locks

---

## 🔄 **Git Workflow**

### **Branch Structure**

```
feature/multi-league  ← Development work happens here
         ↓
      staging        ← Merge for testing with production-like data
         ↓
       main          ← Final merge after full testing
```

### **Commit Strategy**

```bash
# Make changes
git add .
git commit -m "🏗️ Add leagues table and migration"

# Push to dev branch
git push origin feature/multi-league

# Railway auto-deploys to Dev environment
```

### **Merging to Staging**

```bash
# Only merge when backward compatibility is PROVEN
git checkout staging
git merge feature/multi-league
git push origin staging

# Test on staging environment
# If all good, merge to main
```

---

## 📊 **Current Status**

### **✅ Phase 1 - Backend Schema (COMPLETE)**

- [x] Database migration SQL created
- [x] Migration Python script created
- [x] SQLAlchemy models updated (League, User, UserPlayer, LeagueCommissioner)
- [x] `league_id` added to Player and Pick models
- [x] Feature branch created (`feature/multi-league`)
- [x] Dev Railway environment created and configured
- [x] Migration ran successfully on dev database

### **✅ Phase 2 - Query Layer Updates (COMPLETE)**

- [x] Created `api/config.py` with `DEFAULT_LEAGUE_ID = 1` constant
- [x] Updated `app/dashboard_data.py` - all functions filter by `league_id`
- [x] Updated `app/live_scores.py` - pick queries filter by `DEFAULT_LEAGUE_ID`
- [x] Updated `app/main.py` - latest pick week query filters by `DEFAULT_LEAGUE_ID`
- [x] Updated `jobs/update_scores.py` - `ScoreUpdater` accepts `league_id` parameter
- [x] Updated `jobs/ingest_personal_sheets.py` - sheets ingestion filters by `league_id`
- [x] Tested backward compatibility - all queries work with multi-league schema
- [x] Pushed to dev environment for testing

### **🚧 Phase 3 - UI Development (IN PROGRESS)**

- [ ] Build league selection UI (dropdown to switch between leagues)
- [ ] Build league creation page
- [ ] Build commissioner dashboard
- [ ] Build invite link generation

### **📋 Next Steps**

1. **Verify Dev Deployment**
   - Check Railway dev deployment logs
   - Verify app starts successfully with multi-league schema
   - Test dashboard functionality on dev URL

2. **Build League Management UI**
   - League selection dropdown in sidebar
   - League creation page (form with name, slug, pick source)
   - Commissioner dashboard (manage players, view stats)
   - Invite code generation and display

3. **Build In-App Picks (Phase 4)**
   - User authentication system
   - Pick submission form
   - Pick validation logic
   - Pick locking when games start

4. **Test Multi-League Functionality**
   - Create second test league
   - Verify data isolation between leagues
   - Test league switching in UI

---

## 🐛 **Common Issues & Solutions**

### **Issue: Migration fails with "relation already exists"**

**Solution:** Safe to ignore if re-running migration. The migration is idempotent.

### **Issue: Dashboard shows 0 players after migration**

**Solution:** Check that queries include `league_id` filter:
```python
# WRONG
players = db.query(Player).all()

# RIGHT
players = db.query(Player).filter(Player.league_id == 1).all()
```

### **Issue: Can't connect to dev database**

**Solution:** Check DATABASE_URL is correct and network allows connection:
```bash
psql $DATABASE_URL -c "SELECT 1"
```

---

## 📞 **Support**

For questions or issues:
1. Check this document first
2. Review migration logs
3. Test against dev database (never production!)
4. Commit changes to `feature/multi-league` branch only

---

**Last Updated:** 2025-10-01
**Status:** Phase 2 - Query Layer Updates Complete ✅
