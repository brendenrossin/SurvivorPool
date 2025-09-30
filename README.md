# NFL Survivor Pool Dashboard 🏈

A production-ready web application for running NFL survivor pools with automated data ingestion, real-time score tracking, and interactive visualizations.

**Live Demo:** [https://nfl-survivor-2025.up.railway.app/](https://nfl-survivor-2025.up.railway.app/)

[![Tech Stack](https://img.shields.io/badge/Python-3.11-blue)](https://python.org)
[![Framework](https://img.shields.io/badge/Streamlit-1.28-red)](https://streamlit.io)
[![Database](https://img.shields.io/badge/PostgreSQL-15-blue)](https://postgresql.org)
[![Hosting](https://img.shields.io/badge/Railway-Deployed-success)](https://railway.app)

## ✨ Features

### Core Functionality
- **📊 Automated Data Ingestion**: Seamlessly syncs with Google Sheets to import weekly picks
- **🏈 Real-Time NFL Scores**: Fetches live game data from ESPN API
- **🎰 Betting Odds Integration**: Real-time point spreads from The Odds API
- **🔄 Scheduled Cron Jobs**: Automated updates during game days (Sundays, Mondays, Thursdays)

### Interactive Dashboard
- **📈 Dynamic Visualizations**:
  - Remaining players donut chart
  - Weekly team picks distribution (stacked bar chart)
  - Historical elimination trends
- **🔍 Player Analytics**:
  - Individual pick history and search
  - Notable picks tracking (underdog wins 🐕, risky choices)
  - Pool insights (Team of Doom, Graveyard view, Elimination tracker)
- **📱 Mobile-Optimized**: Responsive design with mobile-first chart configurations

### Technical Highlights
- **⚡ Performance**: Streamlit caching for sub-second load times
- **💰 Cost-Effective**: Optimized for free-tier hosting (Railway, Fly.io)
- **🛡️ Robust Error Handling**: Graceful fallbacks and comprehensive logging
- **🎨 Custom Styling**: Team colors and logos for enhanced visual appeal

## Quick Start

### 1. Environment Setup

```bash
# Clone and navigate to project
cd survivor-pool-dashboard

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Database Setup

Set up a PostgreSQL database (local or hosted like Supabase):

```bash
# Apply database schema
psql $DATABASE_URL -f db/migrations.sql
```

### 3. Environment Configuration

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

Required environment variables:
- `DATABASE_URL`: PostgreSQL connection string
- `GOOGLE_SHEETS_SPREADSHEET_ID`: Your Google Sheets ID
- `GOOGLE_SERVICE_ACCOUNT_JSON_BASE64`: Base64-encoded service account JSON
- `NFL_SEASON`: Current NFL season (e.g., 2025)

Optional (for enhanced features):
- `THE_ODDS_API_KEY`: The Odds API key for betting spreads (free tier available)

### 4. Google Sheets Setup

1. Create a Google Cloud Service Account
2. Download the JSON credentials file
3. Encode it to base64: `base64 -i credentials.json`
4. Set the encoded value in `GOOGLE_SERVICE_ACCOUNT_JSON_BASE64`
5. Share your Google Sheet with the service account email (read-only)

### 5. Initialize Data

```bash
# Backfill historical weeks (1-2)
python jobs/backfill_weeks.py --weeks 1 2

# Ingest current picks
python jobs/ingest_sheet.py

# Update scores
python jobs/update_scores.py
```

### 6. Run Dashboard

```bash
streamlit run app/main.py
```

Visit `http://localhost:8501` to see your dashboard!

## 📁 Project Structure

```
survivor-pool/
├── app/                    # 🎨 Streamlit dashboard application
│   ├── main.py            #    Main dashboard entry point
│   ├── dashboard_data.py  #    Cached data fetching layer
│   └── live_scores.py     #    Live game status widgets
├── api/                   # 🔌 Core API and data models
│   ├── database.py        #    Database connection & session management
│   ├── models.py          #    SQLAlchemy ORM models
│   ├── sheets.py          #    Google Sheets integration
│   ├── oauth_manager.py   #    OAuth token refresh automation
│   └── score_providers.py #    NFL data provider interfaces (ESPN, SportRadar)
├── jobs/                  # ⚙️ Background worker jobs
│   ├── ingest_sheet.py    #    Google Sheets → Database sync
│   ├── update_scores.py   #    NFL scores ingestion
│   ├── update_odds.py     #    Betting odds ingestion
│   └── backfill_weeks.py  #    Historical data backfill utility
├── db/                    # 🗄️ Database schemas and seeds
│   ├── migrations.sql     #    PostgreSQL schema definition
│   └── seed_team_map.json #    NFL team colors/logos metadata
├── scripts/               # 🛠️ Development and utility scripts
├── cron/                  # 📅 Railway cron job configurations
├── public/logos/          # 🏈 NFL team logos (optional)
├── .credentials/          # 🔐 OAuth tokens and service accounts (gitignored)
├── Dockerfile             # 🐳 Container build configuration
├── start.sh               # 🚀 Railway startup script
└── railway*.toml          # 🚂 Railway service configurations (DO NOT MOVE!)
```

> **Note:** The `railway*.toml` files **must** remain in the root directory for Railway deployment to function properly.

## Google Sheets Format

Your Google Sheets should follow this format:

| Name         | Week 1 | Week 2 | Week 3 | ... |
|--------------|--------|--------|--------|-----|
| Player 1     | BUF    | KC     | PHI    | ... |
| Player 2     | DAL    | GB     | BAL    | ... |

- Column A: Player display names (unique)
- Columns B+: Week picks using NFL team abbreviations (BUF, KC, PHI, etc.)

## Deployment

### Option 1: Railway (Recommended)

1. Connect your GitHub repo to Railway
2. Set environment variables in Railway dashboard
3. Railway will automatically build and deploy

### Option 2: Fly.io

Create a `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "app/main.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

Deploy:
```bash
fly deploy
```

## Scheduled Jobs

Set up cron jobs for automated updates:

### Sheet Ingestion
- **Daily**: 7:00 AM PT
- **Sundays**: Additional run at 9:30 AM PT

### Score Updates
- **Sundays**: Hourly from 10:00 AM - 9:00 PM PT
- **Monday/Thursday**: Once at 9:00 PM PT

Example cron entries:
```bash
# Sheet ingestion - daily 7am PT
0 14 * * * /path/to/python /path/to/jobs/ingest_sheet.py

# Sheet ingestion - Sunday 9:30am PT
30 16 * * 0 /path/to/python /path/to/jobs/ingest_sheet.py

# Score updates - Sunday hourly 10am-9pm PT
0 17-4 * * 0 /path/to/python /path/to/jobs/update_scores.py

# Score updates - Mon/Thu 9pm PT
0 4 * * 1,4 /path/to/python /path/to/jobs/update_scores.py
```

## Manual Operations

### Backfill Additional Weeks
```bash
python jobs/backfill_weeks.py --weeks 3 4 5
```

### Force Sheet Refresh
```bash
python jobs/ingest_sheet.py
```

### Update Scores Manually
```bash
python jobs/update_scores.py
```

### Database Initialization
```bash
python -c "from api.database import init_db; init_db()"
```

## Troubleshooting

### Common Issues

1. **Database Connection Errors**
   - Verify `DATABASE_URL` is correct
   - Ensure database is accessible from your environment

2. **Google Sheets Access Denied**
   - Verify service account has access to the sheet
   - Check that `GOOGLE_SERVICE_ACCOUNT_JSON_BASE64` is properly encoded

3. **ESPN API Issues**
   - ESPN's unofficial API can be unreliable
   - Check logs for specific error messages
   - Consider switching to a paid NFL data provider

4. **Missing Team Logos**
   - Team logos are optional
   - Place PNG files in `public/logos/` named by team abbreviation (e.g., `BUF.png`)

### Logs and Monitoring

Job metadata is stored in the `job_meta` table:
```sql
SELECT * FROM job_meta ORDER BY last_run_at DESC;
```

## 🏗️ Architecture & Design Decisions

### Database-First Architecture
All data flows through PostgreSQL with no real-time API calls in the UI, ensuring consistent performance and reducing external API dependency.

### Caching Strategy
Aggressive use of Streamlit's `@st.cache_data` and `@st.cache_resource` decorators for sub-second page loads, with intelligent TTL settings (60s for live data, longer for static data).

### Mobile-First Design
Charts and UI components are optimized for mobile viewing with:
- Limited annotation density
- Touch-friendly controls
- Responsive layouts

### Cost Optimization
Designed to run on free-tier infrastructure:
- Minimal database queries with proper indexing
- Efficient cron job scheduling (only during game windows)
- SQLAlchemy session management to prevent connection leaks

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

## 📄 License

MIT License - feel free to use this project for your own survivor pools!

---

**Built with ❤️ for NFL fans by Brent Rossin**

*Questions or feedback? Open an issue or reach out!*