#!/usr/bin/env python3
"""
Daily odds update job - fetches betting odds and updates database
Run once daily at 8am to minimize API usage
"""

import os
import sys
from datetime import datetime, timezone
from sqlalchemy.orm import Session

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.database import SessionLocal
from api.models import Game, JobMeta
from api.odds_providers import get_odds_provider
from dotenv import load_dotenv

load_dotenv()

class OddsUpdater:
    def __init__(self):
        odds_provider_name = os.getenv("ODDS_PROVIDER", "the_odds_api")
        self.odds_provider = get_odds_provider(odds_provider_name)
        self.season = int(os.getenv("NFL_SEASON", 2025))

    def run(self):
        """Main odds update process"""
        db = SessionLocal()
        try:
            print(f"🎰 Starting odds update at {datetime.now()}")

            # Update job meta
            self.update_job_meta(db, "update_odds", "running", "Starting odds update")

            # Get current week (odds are usually available for multiple weeks)
            current_week = self.get_current_week()
            print(f"Updating odds for Season {self.season}, Week {current_week}")

            # Fetch betting odds for current week
            odds_data = self.odds_provider.get_nfl_odds(self.season, current_week)

            if not odds_data:
                print("⚠️ No odds data received - API key may be missing")
                self.update_job_meta(db, "update_odds", "warning", "No odds data received")
                return

            # Update games with odds
            games_updated = self.update_games_with_odds(db, current_week, odds_data)

            db.commit()

            message = f"Updated odds for {games_updated} games in week {current_week}"
            self.update_job_meta(db, "update_odds", "success", message)

            print(f"✅ Odds update completed: {message}")

        except Exception as e:
            db.rollback()
            error_msg = f"Error during odds update: {str(e)}"
            self.update_job_meta(db, "update_odds", "error", error_msg)
            print(f"❌ {error_msg}")
            return False
        finally:
            db.close()

    def get_current_week(self) -> int:
        """Get current NFL week - simple logic for now"""
        # In a real implementation, you might want to derive this from ESPN or another source
        # For now, we'll use a simple approach
        now = datetime.now()
        # NFL season typically starts first Thursday of September
        # Week 1 starts around Sept 5-10, so rough calculation
        if now.month >= 9:  # September or later
            week = min(18, max(1, (now.day - 1) // 7 + 1))
        elif now.month <= 2:  # January-February (playoffs)
            week = min(22, 19 + now.month)  # Rough playoff weeks
        else:
            week = 1  # Off-season default

        return week

    def update_games_with_odds(self, db: Session, week: int, odds_data: dict) -> int:
        """Update existing games with odds data"""
        updated_count = 0

        # Get all games for the current week
        games = db.query(Game).filter(
            Game.season == self.season,
            Game.week == week
        ).all()

        for game in games:
            # Create a key to match with odds data
            game_key = f"{game.away_team}_at_{game.home_team}"

            # Check if we have odds for this game
            if game_key in odds_data:
                odds = odds_data[game_key]

                # Only update if we have new/different odds (preserve historical data)
                new_spread = odds.get("point_spread")
                new_favorite = odds.get("favorite_team")

                updated = False
                # Only update spread if we have new data (don't overwrite with None)
                if new_spread is not None and game.point_spread != new_spread:
                    game.point_spread = new_spread
                    updated = True

                # Only update favorite if we have new data (don't overwrite with None)
                if new_favorite is not None and game.favorite_team != new_favorite:
                    game.favorite_team = new_favorite
                    updated = True

                if updated:
                    updated_count += 1
                    print(f"🎰 Updated odds: {game.away_team} @ {game.home_team} - {new_favorite} -{new_spread}")

        return updated_count

    def update_job_meta(self, db: Session, job_name: str, status: str, message: str):
        """Update job metadata"""
        job_meta = db.query(JobMeta).filter(JobMeta.job_name == job_name).first()

        if not job_meta:
            job_meta = JobMeta(job_name=job_name)
            db.add(job_meta)

        job_meta.last_run_at = datetime.now(timezone.utc)
        job_meta.status = status
        job_meta.message = message

        if status == "success":
            job_meta.last_success_at = datetime.now(timezone.utc)

        db.commit()

if __name__ == "__main__":
    updater = OddsUpdater()
    updater.run()