# Railway Staging & Production Deployment Setup

## Overview
This setup provides a staging environment for testing changes before production deployment, with automated CI/CD pipeline.

## Architecture
- **Staging**: Auto-deploys on every push to `main` branch
- **Production**: Manual deployment after staging verification
- **Cron Jobs**: Separate services for each environment

## 1. Railway Project Setup

### Main Services (per environment)
1. **Web App** (staging & production)
2. **Odds Cron** (staging & production)
3. **Scores Cron** (staging & production)
4. **Sheets Cron** (staging & production)

### Database Setup
- **Staging**: Separate PostgreSQL database
- **Production**: Separate PostgreSQL database
- Each environment has isolated data

## 2. GitHub Secrets Configuration

Add these secrets to your GitHub repository:

### Railway Webhooks
```
RAILWAY_STAGING_WEBHOOK=https://webhooks.railway.app/...
RAILWAY_PRODUCTION_WEBHOOK=https://webhooks.railway.app/...
STAGING_URL=https://your-staging-app.up.railway.app
PRODUCTION_URL=https://your-production-app.up.railway.app
```

## 3. Railway Environment Variables

### Required for All Services (both staging & production):
```
DATABASE_URL=(auto-set by Railway)
GOOGLE_SHEETS_SPREADSHEET_ID=your_spreadsheet_id
GOOGLE_SERVICE_ACCOUNT_JSON_BASE64=your_base64_encoded_json
NFL_SEASON=2025
```

### Required for Odds Services:
```
THE_ODDS_API_KEY=your_api_key
```

### Environment-Specific:
```
ENVIRONMENT=staging|production
```

## 4. Deployment Workflow

### Automatic Staging Deployment
1. Push code to `main` branch
2. GitHub Action automatically deploys to staging
3. Staging URL updated with new version
4. Test staging environment

### Manual Production Deployment
1. Go to GitHub Actions → "Deploy to Railway"
2. Click "Run workflow"
3. Select "production" environment
4. Production deployment starts
5. Verification checks run automatically

## 5. Railway Service Configuration

### Main Web App Services
- **Start Command**: `bash start.sh`
- **Builder**: nixpacks
- **Auto-deploy**: Connect to GitHub repository

### Cron Services Configuration

#### Odds Update Service
```toml
[build]
builder = "nixpacks"

[deploy]
startCommand = "python cron/daily_odds_update.py"
cronSchedule = "0 13 * * *"  # 8:00 AM EST daily
```

#### Score Update Service
```toml
[build]
builder = "nixpacks"

[deploy]
startCommand = "python cron/score_update.py"
cronSchedule = "0 17,18,19,20,21,22,23,0,1,2 * * 0,1"  # Sunday hourly + Monday night
```

#### Sheets Ingestion Service
```toml
[build]
builder = "nixpacks"

[deploy]
startCommand = "python cron/sheets_ingestion.py"
cronSchedule = "0 14 * * *"  # 9:00 AM EST daily
```

## 6. Testing Process

### Staging Verification Checklist
- [ ] App loads without errors
- [ ] Database migration completed successfully
- [ ] Live scores display properly (with/without betting lines)
- [ ] Cron jobs can run manually without errors
- [ ] Mobile UI displays correctly
- [ ] No console errors in browser

### Production Deployment Checklist
- [ ] Staging tests passed completely
- [ ] Database backup completed (if needed)
- [ ] Cron job schedules verified
- [ ] Environment variables confirmed
- [ ] Rollback plan prepared

## 7. Rollback Strategy

### If Production Deployment Fails:
1. **Immediate**: Revert Railway to previous deployment
2. **GitHub**: Create hotfix branch and deploy to staging first
3. **Database**: Restore from backup if schema changes involved

### If Cron Jobs Fail:
1. Check Railway service logs
2. Verify environment variables
3. Test cron scripts manually
4. Check API rate limits and credentials

## 8. Monitoring

### Key Metrics to Monitor:
- **App Health**: HTTP response codes from health checks
- **Database**: Connection errors, query performance
- **Cron Jobs**: Exit codes, execution duration
- **APIs**: The Odds API usage (500 credits/month limit)

### Log Locations:
- **Railway Logs**: Each service → Logs tab
- **GitHub Actions**: Actions → Deploy to Railway workflow
- **Application Logs**: Streamlit console output

## 9. Cost Optimization

### Railway Usage:
- **Staging**: Shared resources, minimal uptime
- **Production**: Dedicated resources, high availability
- **Cron Jobs**: Only run when needed, exit cleanly

### API Usage:
- **The Odds API**: ~30 calls/month total across both environments
- **ESPN API**: Free tier, rate limited to 8 req/min

## 10. Security

### Environment Isolation:
- Separate databases prevent data leakage
- Different API keys for staging vs production
- Limited access to production environment

### Secrets Management:
- All sensitive data in environment variables
- No secrets committed to repository
- Rotate API keys regularly

## Next Steps

1. Set up Railway staging and production services
2. Configure GitHub secrets and environment variables
3. Test staging deployment pipeline
4. Configure cron jobs for both environments
5. Perform end-to-end testing
6. Deploy to production

The staging environment allows safe testing of database migrations, new features, and cron job changes before affecting production users.