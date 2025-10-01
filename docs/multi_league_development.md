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

### **Step 1: Create Dev Railway Environment**

1. Go to Railway dashboard: https://railway.app
2. Create **New Project** → "SurvivorPool-Dev"
3. Add **PostgreSQL** service (separate from production)
4. Add **Web Service** and connect to GitHub
5. Configure deployment settings:
   - **Branch**: `feature/multi-league`
   - **Start Command**: `./start.sh`
   - **Root Directory**: `/`

### **Step 2: Set Environment Variables (Dev Railway)**

```bash
# Database
DATABASE_URL=<your-dev-postgres-url>

# NFL Season
NFL_SEASON=2025

# Google Sheets (optional for testing)
GOOGLE_SHEETS_SPREADSHEET_ID=<test-sheet-id>
GOOGLE_SERVICE_ACCOUNT_JSON_BASE64=<service-account-creds>

# Commissioner Email (for default league)
COMMISSIONER_EMAIL=your-email@example.com

# Development Flag
IS_DEV_ENV=true

# Port (Railway sets this automatically)
PORT=8080
```

### **Step 3: Run Migration on Dev Database**

```bash
# Locally, pointing to dev database
export DATABASE_URL="<dev-database-url>"
python scripts/migrate_to_multi_league.py
```

Or on Railway (via exec):
```bash
railway run python scripts/migrate_to_multi_league.py
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

### **✅ Completed**

- [x] Database migration SQL created
- [x] Migration Python script created
- [x] SQLAlchemy models updated (League, User, UserPlayer, LeagueCommissioner)
- [x] `league_id` added to Player and Pick models
- [x] Feature branch created (`feature/multi-league`)

### **🚧 In Progress**

- [ ] Run migration on dev database
- [ ] Update all queries to filter by league_id
- [ ] Test backward compatibility
- [ ] Create Dev Railway environment

### **📋 Next Steps**

1. **Deploy to Dev Railway**
   - Create new Railway project
   - Point to `feature/multi-league` branch
   - Run migration on dev database

2. **Update Query Layer**
   - Add `DEFAULT_LEAGUE_ID = 1` constant
   - Update all `db.query(Player)` → `db.query(Player).filter(Player.league_id == league_id)`
   - Update sheets ingestion to use league_id

3. **Test Backward Compatibility**
   - Ensure existing dashboard works identically
   - Verify data integrity after migration

4. **Build League Management UI**
   - League creation page
   - Commissioner dashboard
   - Invite link generation

5. **Build In-App Picks**
   - User authentication
   - Pick submission form
   - Pick validation logic

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

**Last Updated:** 2025-01-10
**Status:** Phase 1 - Backend Schema Complete
