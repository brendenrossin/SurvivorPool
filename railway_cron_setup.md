# Railway Cron Jobs Setup

After deploying to Railway, you'll need to set up cron jobs for automated data updates.

## Method 1: Railway Cron (Recommended)

In your Railway dashboard:

1. **Go to your project → Add Service → Cron**
2. **Create these cron jobs:**

### Sheet Ingestion (Daily 7 AM PT)
```bash
# Name: sheet-ingestion-daily
# Schedule: 0 14 * * * (7 AM PT = 2 PM UTC)
# Command: python jobs/ingest_sheet.py
```

### Sheet Ingestion (Sunday 9:30 AM PT)
```bash
# Name: sheet-ingestion-sunday
# Schedule: 30 16 * * 0 (9:30 AM PT = 4:30 PM UTC on Sunday)
# Command: python jobs/ingest_sheet.py
```

### Score Updates (Sunday Hourly 10 AM - 9 PM PT)
```bash
# Name: scores-sunday-hourly
# Schedule: 0 17-4 * * 0 (10 AM - 9 PM PT = 5 PM - 4 AM UTC on Sunday)
# Command: python jobs/update_scores.py
```

### Score Updates (Monday/Thursday 9 PM PT)
```bash
# Name: scores-weeknight
# Schedule: 0 4 * * 1,4 (9 PM PT = 4 AM UTC next day)
# Command: python jobs/update_scores.py
```

## Method 2: GitHub Actions (Free Alternative)

If Railway cron costs too much, we can use GitHub Actions:

1. Create `.github/workflows/cron-jobs.yml`
2. Use repository secrets for environment variables
3. Jobs run and call Railway API endpoints

Let me know which approach you prefer!