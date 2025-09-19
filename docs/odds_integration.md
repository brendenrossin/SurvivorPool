# Betting Odds Integration Guide

## Overview
The survivor pool dashboard now integrates real-time NFL betting odds to enhance the "Big Balls" picks section and live scores display. This integration uses The Odds API to fetch point spreads and identify underdog victories.

## Features Added

### 🎯 Enhanced Big Balls Section
- **Before**: Only showed road wins (away teams that won)
- **After**: Shows both road wins AND underdog victories based on Vegas spreads
- **Dog Emoji**: 🐕 appears next to teams that were underdogs and won
- **Spread Info**: Displays point spread for context ("underdog by 3.5 pts")

### 📺 Live Scores Enhancement
- **Pregame Games**: Shows betting spreads instead of just "vs"
- **Format**: "vs (BUF -3.5)" indicates Buffalo favored by 3.5 points
- **Real-time**: Updates as games start and spreads become live scores

### 🗄️ Database Schema
New columns added to `games` table:
- `point_spread` (Float): Point spread value (positive = home team favored)
- `favorite_team` (String): Which team is favored according to spread

## API Integration

### The Odds API
- **Provider**: https://the-odds-api.com/
- **Free Tier**: 500 credits per month
- **Season Usage**: ~320 calls (16 games × 20 weeks)
- **Cost**: FREE for survivor pool usage

### Supported Sportsbooks
- DraftKings (preferred)
- FanDuel
- BetMGM
- Caesars
- Bovada

## Setup Instructions

### 1. Get API Key
1. Visit https://the-odds-api.com/
2. Sign up for free account
3. Get your API key from dashboard

### 2. Local Environment
Add to your `.env` file:
```bash
THE_ODDS_API_KEY=your_api_key_here
```

### 3. Railway Environment
Add environment variable in Railway dashboard:
- **Variable**: `THE_ODDS_API_KEY`
- **Value**: Your API key

### 4. Test Integration
```bash
# Test without API key (safe)
python scripts/testing/test_odds_integration.py

# Test with API key (uses credits)
python scripts/testing/test_full_odds_integration.py

# Update scores with odds
python jobs/update_scores.py
```

## How It Works

### Data Flow
1. **Score Updater** runs (cron job or manual)
2. **ESPN API** fetches game scores and status
3. **The Odds API** fetches point spreads for same games
4. **Merge Logic** matches games by team names
5. **Database** stores both scores and odds
6. **Dashboard** displays enhanced data

### Team Matching
Games are matched between ESPN and The Odds API using:
```
{away_team}_at_{home_team}
```
Example: `MIA_at_BUF` matches Miami @ Buffalo

### Underdog Detection
A team is considered an underdog if:
- We have spread data (`point_spread` and `favorite_team` not null)
- The picked team is NOT the `favorite_team`
- The picked team won the game

## Code Architecture

### Key Files
- `api/odds_providers.py` - The Odds API integration
- `jobs/update_scores.py` - Enhanced score updater
- `app/dashboard_data.py` - Big Balls logic with spreads
- `app/live_scores.py` - Live scores with spreads

### Rate Limiting
- Uses existing rate limiter with 30-minute caching
- Respects The Odds API rate limits
- Graceful fallback if API fails

### Error Handling
- No API key = no odds (shows road wins only)
- API failure = continues with scores only
- Missing spread data = falls back to road win logic

## Testing

### Automated Tests
```bash
# Basic integration test
python scripts/testing/test_odds_integration.py

# Comprehensive test
python scripts/testing/test_full_odds_integration.py
```

### Manual Testing
1. Check Big Balls section for 🐕 emoji
2. Verify live scores show spreads for pregame games
3. Monitor logs for odds API calls
4. Confirm database has spread data

## Monitoring

### API Usage
Track credits in The Odds API dashboard:
- **Expected**: ~20 calls per week during season
- **Limit**: 500 calls per month (free tier)
- **Alert**: Set up alerts at 400 credits used

### Logs
Look for these log messages:
```
🎰 Fetching NFL odds from The Odds API...
✅ Odds API: Fetched odds for X games
🎰 Added odds: MIA @ BUF - BUF -3.5
```

## Fallback Behavior

### Without API Key
- Big Balls shows road wins only
- Live scores show "vs" for pregame
- No errors or crashes

### API Failures
- Continues with ESPN scores
- Shows road wins in Big Balls
- Logs warning but doesn't break

### Missing Spread Data
- Falls back to road win detection
- No 🐕 emoji shown
- Dashboard remains functional

## Cost Analysis

### Free Tier Usage
- **Per Game**: 1 API call
- **Per Week**: ~16 calls (NFL games)
- **Per Month**: ~64 calls (4 weeks)
- **Per Season**: ~320 calls total
- **Free Limit**: 500 calls/month ✅

### Paid Tier (if needed)
- **20K Plan**: $30/month
- **Usage**: Way under limit
- **ROI**: Enhanced user experience

## Future Enhancements

### Possible Additions
- **Live Survivorship Calculator**: Real-time odds-based survival chances
- **Upset Tracker**: Biggest point spread upsets of the week
- **Confidence Ratings**: How "safe" picks are based on Vegas lines
- **Weekly Risk Report**: Show who's picking risky underdogs

### API Considerations
- Monitor usage as features expand
- Consider caching strategies for repeated calls
- Evaluate other odds providers if needed

## Troubleshooting

### Common Issues

**No odds showing in dashboard:**
- Check THE_ODDS_API_KEY is set
- Verify API key is valid
- Check logs for API errors

**Big Balls shows no underdogs:**
- Early season issue - few underdogs picked
- Check if spread data exists in database
- Verify underdog detection logic

**Live scores missing spreads:**
- Check if games have spread data
- Verify pregame status
- Confirm API returned spread for those games

### Debug Commands
```bash
# Check database for odds data
python -c "
from api.database import SessionLocal
from api.models import Game
db = SessionLocal()
odds_games = db.query(Game).filter(Game.point_spread.isnot(None)).count()
print(f'Games with odds: {odds_games}')
db.close()
"

# Test API connection
python -c "
from api.odds_providers import get_odds_provider
provider = get_odds_provider()
odds = provider.get_nfl_odds(2025, 3)
print(f'Odds fetched for {len(odds)} games')
"
```