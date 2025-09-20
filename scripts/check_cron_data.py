#!/usr/bin/env python3
"""
Check if cron jobs are working by analyzing database data patterns
"""

import os
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

def check_cron_effectiveness():
    """Check if cron jobs are working based on data freshness"""

    from sqlalchemy import create_engine, text

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ DATABASE_URL not found")
        return

    engine = create_engine(database_url)

    print("🔍 Checking Cron Job Effectiveness via Data Analysis")
    print("=" * 60)

    with engine.connect() as conn:

        # 1. Check Odds Update Cron (should run daily)
        print("\n📊 ODDS UPDATE CRON CHECK:")
        odds_result = conn.execute(text("""
            SELECT
                COUNT(*) as total_games,
                COUNT(CASE WHEN point_spread IS NOT NULL THEN 1 END) as games_with_odds,
                COUNT(CASE WHEN favorite_team IS NOT NULL THEN 1 END) as games_with_favorites
            FROM games
            WHERE season = 2025 AND week >= 3
        """)).fetchone()

        odds_percentage = (odds_result.games_with_odds / odds_result.total_games * 100) if odds_result.total_games > 0 else 0

        print(f"  Games with odds: {odds_result.games_with_odds}/{odds_result.total_games} ({odds_percentage:.1f}%)")

        if odds_percentage > 80:
            print("  ✅ Odds cron appears to be working (>80% coverage)")
        elif odds_percentage > 50:
            print("  ⚠️  Odds cron partially working (50-80% coverage)")
        else:
            print("  ❌ Odds cron not working (<50% coverage)")

        # 2. Check Score Update Cron (should run frequently during games)
        print("\n🏈 SCORE UPDATE CRON CHECK:")
        scores_result = conn.execute(text("""
            SELECT
                COUNT(*) as total_games,
                COUNT(CASE WHEN home_score IS NOT NULL OR away_score IS NOT NULL THEN 1 END) as games_with_scores,
                COUNT(CASE WHEN winner_abbr IS NOT NULL THEN 1 END) as completed_games
            FROM games
            WHERE season = 2025 AND week <= 3
        """)).fetchone()

        score_percentage = (scores_result.games_with_scores / scores_result.total_games * 100) if scores_result.total_games > 0 else 0

        print(f"  Games with scores: {scores_result.games_with_scores}/{scores_result.total_games} ({score_percentage:.1f}%)")
        print(f"  Completed games: {scores_result.completed_games}")

        if score_percentage > 90:
            print("  ✅ Score cron working well (>90% have scores)")
        elif score_percentage > 70:
            print("  ⚠️  Score cron partially working (70-90%)")
        else:
            print("  ❌ Score cron issues (<70% have scores)")

        # 3. Check Sheets Ingestion Cron (should run daily)
        print("\n📋 SHEETS INGESTION CRON CHECK:")
        sheets_result = conn.execute(text("""
            SELECT
                COUNT(DISTINCT player_id) as total_players,
                COUNT(*) as total_picks,
                COUNT(CASE WHEN week >= 3 THEN 1 END) as recent_picks
            FROM picks
            WHERE season = 2025
        """)).fetchone()

        print(f"  Total players: {sheets_result.total_players}")
        print(f"  Total picks: {sheets_result.total_picks}")
        print(f"  Recent picks (week 3+): {sheets_result.recent_picks}")

        if sheets_result.total_players > 15 and sheets_result.total_picks > 100:
            print("  ✅ Sheets cron working (good player/pick counts)")
        elif sheets_result.total_players > 5:
            print("  ⚠️  Sheets cron partially working (some data)")
        else:
            print("  ❌ Sheets cron not working (minimal data)")

        # 4. Check Pick Results Processing
        print("\n🎯 PICK RESULTS PROCESSING CHECK:")
        results_check = conn.execute(text("""
            SELECT
                COUNT(*) as total_picks,
                COUNT(CASE WHEN pr.survived IS NOT NULL THEN 1 END) as processed_picks,
                COUNT(CASE WHEN pr.survived = true THEN 1 END) as surviving_picks,
                COUNT(CASE WHEN pr.survived = false THEN 1 END) as eliminated_picks
            FROM picks p
            LEFT JOIN pick_results pr ON p.pick_id = pr.pick_id
            WHERE p.season = 2025 AND p.week <= 3
        """)).fetchone()

        processing_percentage = (results_check.processed_picks / results_check.total_picks * 100) if results_check.total_picks > 0 else 0

        print(f"  Processed picks: {results_check.processed_picks}/{results_check.total_picks} ({processing_percentage:.1f}%)")
        print(f"  Surviving: {results_check.surviving_picks}")
        print(f"  Eliminated: {results_check.eliminated_picks}")

        if processing_percentage > 80:
            print("  ✅ Pick processing working well")
        else:
            print("  ⚠️  Pick processing needs attention")

        # Overall assessment
        print("\n" + "=" * 60)
        print("📋 OVERALL ASSESSMENT:")

        working_crons = 0
        if odds_percentage > 50: working_crons += 1
        if score_percentage > 70: working_crons += 1
        if sheets_result.total_players > 5: working_crons += 1

        print(f"  Working crons: {working_crons}/3")

        if working_crons == 3:
            print("  🎉 All cron jobs appear to be working!")
        elif working_crons >= 2:
            print("  ⚠️  Most cron jobs working, some issues")
        else:
            print("  🚨 Multiple cron job issues detected")

        print("\n💡 Next steps:")
        if working_crons < 3:
            print("  • Check Railway service logs for errors")
            print("  • Verify environment variables are set")
            print("  • Try manual execution: railway run python cron/[script].py")
        print("  • Run: python scripts/monitor_cron_jobs.py for detailed health check")

if __name__ == "__main__":
    check_cron_effectiveness()