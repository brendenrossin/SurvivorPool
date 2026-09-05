# Survivor Pool Dashboard

A cheap-to-run, single-page web app that auto-ingests weekly picks from Google Sheets, fetches live NFL scores, determines who "survived," and renders fun, shareable visuals.

## Features

- 📊 **Google Sheets Integration**: Automatically ingests picks from Google Sheets
- 🏈 **Live NFL Scores**: Fetches real-time game data from ESPN
- 🎰 **Betting Odds Integration**: Real-time point spreads from The Odds API (free tier)
- 📈 **Interactive Dashboard**: Streamlit-based dashboard with:
  - Remaining players donut chart
  - Weekly picks grid (teams × weeks, leading with the current week)
  - Player search and history
  - Notable picks (dumbest picks, underdog wins with 🐕 emoji)
  - Pool insights (Team of Doom, Graveyard, Elimination Tracker)
- 🔄 **Automated Jobs**: Scheduled data ingestion and score updates
- 🚀 **Lightweight**: Designed for free-tier hosting (Railway, Fly.io, etc.)

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

## Project Structure

```
survivor-dashboard/
├── app/                    # Streamlit dashboard
│   ├── main.py            # Main dashboard app
│   └── dashboard_data.py  # Data fetching functions
├── api/                   # Core API and data models
│   ├── database.py        # Database connection
│   ├── models.py          # SQLAlchemy models
│   ├── sheets.py          # Google Sheets client
│   └── score_providers.py # NFL data providers
├── jobs/                  # Background jobs
│   ├── ingest_sheet.py    # Google Sheets ingestion
│   ├── update_scores.py   # NFL scores updates
│   └── backfill_weeks.py  # Historical data backfill
├── db/                    # Database files
│   ├── migrations.sql     # Database schema
│   └── seed_team_map.json # Team colors and metadata
├── public/logos/          # Team logos (optional)
├── requirements.txt       # Python dependencies
└── .env.example          # Environment template
```

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

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test locally
5. Submit a pull request

## License

MIT License - see LICENSE file for details.