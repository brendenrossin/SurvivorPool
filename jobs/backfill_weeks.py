#!/usr/bin/env python3
"""
Backfill job - backfills weeks 1-2 data for initial setup
"""

import os
import sys
from datetime import datetime, timezone
from sqlalchemy.orm import Session

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.database import SessionLocal
from api.models import Game, Pick, PickResult, Player, JobMeta
from api.score_providers import get_score_provider
from api.sheets import GoogleSheetsClient
from dotenv import load_dotenv

load_dotenv()

class BackfillProcessor:
    def __init__(self):
        provider_name = os.getenv("SCORES_PROVIDER", "espn")
        self.score_provider = get_score_provider(provider_name)
        self.sheets_client = GoogleSheetsClient()
        self.season = int(os.getenv("NFL_SEASON", 2025))

    def run(self, weeks_to_backfill: list = [1, 2]):
        """Main backfill process"""
        db = SessionLocal()
        try:
            print(f"Starting backfill for weeks {weeks_to_backfill} at {datetime.now()}")

            # Update job meta
            self.update_job_meta(db, "backfill_weeks", "running", f"Starting backfill for weeks {weeks_to_backfill}")

            total_games = 0
            total_picks = 0

            for week in weeks_to_backfill:
                print(f"Processing week {week}...")

                # 1. Fetch and store official week schedules and finals
                games = self.score_provider.get_schedule_and_scores(self.season, week)
                games_count = self.upsert_games(db, games)
                total_games += games_count

                # 2. Ingest sheet data for this week
                picks_count = self.ingest_picks_for_week(db, week)
                total_picks += picks_count

                # 3. Mark picks as locked and compute survived status
                results_count = self.process_pick_results(db, week)

                print(f"Week {week}: {games_count} games, {picks_count} picks, {results_count} results processed")

            db.commit()

            message = f"Backfilled {len(weeks_to_backfill)} weeks: {total_games} games, {total_picks} picks processed"
            self.update_job_meta(db, "backfill_weeks", "success", message)

            print(f"Backfill completed: {message}")

        except Exception as e:
            db.rollback()
            error_msg = f"Error during backfill: {str(e)}"
            self.update_job_meta(db, "backfill_weeks", "error", error_msg)
            print(error_msg)
            raise
        finally:
            db.close()

    def upsert_games(self, db: Session, games: list) -> int:
        """Create or update games in database"""
        updated_count = 0

        for game_data in games:
            existing_game = db.query(Game).filter(Game.game_id == game_data.game_id).first()

            if existing_game:
                # Update existing game
                existing_game.status = game_data.status
                existing_game.home_score = game_data.home_score
                existing_game.away_score = game_data.away_score
                existing_game.winner_abbr = game_data.winner_abbr
            else:
                # Create new game
                new_game = Game(
                    game_id=game_data.game_id,
                    season=game_data.season,
                    week=game_data.week,
                    kickoff=game_data.kickoff,
                    home_team=game_data.home_team,
                    away_team=game_data.away_team,
                    status=game_data.status,
                    home_score=game_data.home_score,
                    away_score=game_data.away_score,
                    winner_abbr=game_data.winner_abbr
                )
                db.add(new_game)
                updated_count += 1

        return updated_count

    def ingest_picks_for_week(self, db: Session, week: int) -> int:
        """Ingest picks from sheet for specific week"""
        # Fetch data from sheets
        raw_data = self.sheets_client.get_picks_data()
        parsed_data = self.sheets_client.parse_picks_data(raw_data)

        # Ensure players exist
        for player_name in parsed_data["players"]:
            existing = db.query(Player).filter(Player.display_name == player_name).first()
            if not existing:
                player = Player(display_name=player_name)
                db.add(player)

        # Process picks for this specific week
        picks_count = 0
        for pick_data in parsed_data["picks"]:
            if pick_data["week"] != week:
                continue

            player = db.query(Player).filter(
                Player.display_name == pick_data["player_name"]
            ).first()

            if not player:
                continue

            # Check if pick already exists
            existing_pick = db.query(Pick).filter(
                Pick.player_id == player.player_id,
                Pick.season == self.season,
                Pick.week == week
            ).first()

            if not existing_pick:
                new_pick = Pick(
                    player_id=player.player_id,
                    season=self.season,
                    week=week,
                    team_abbr=pick_data["team_abbr"]
                )
                db.add(new_pick)
                picks_count += 1

        return picks_count

    def process_pick_results(self, db: Session, week: int) -> int:
        """Process pick results for a week - link to games, lock, and compute survival"""
        results_count = 0

        # Get all picks for this week
        picks = db.query(Pick).filter(
            Pick.season == self.season,
            Pick.week == week,
            Pick.team_abbr.isnot(None)
        ).all()

        for pick in picks:
            # Find the game for this pick
            game = db.query(Game).filter(
                Game.season == pick.season,
                Game.week == pick.week,
                ((Game.home_team == pick.team_abbr) | (Game.away_team == pick.team_abbr))
            ).first()

            if not game:
                continue

            # Get or create pick result
            pick_result = db.query(PickResult).filter(
                PickResult.pick_id == pick.pick_id
            ).first()

            if not pick_result:
                pick_result = PickResult(pick_id=pick.pick_id)
                db.add(pick_result)

            # Link to game
            pick_result.game_id = game.game_id

            # Mark as locked (since we're backfilling, games have already started)
            pick_result.is_locked = True

            # Validate pick (check for duplicate teams)
            duplicate_picks = db.query(Pick).filter(
                Pick.player_id == pick.player_id,
                Pick.season == pick.season,
                Pick.team_abbr == pick.team_abbr,
                Pick.pick_id != pick.pick_id
            ).count()

            pick_result.is_valid = (duplicate_picks == 0)

            # Compute survival status if game is final
            if game.status == "final" and game.winner_abbr is not None:
                pick_result.survived = (pick.team_abbr == game.winner_abbr)

            results_count += 1

        return results_count

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
    import argparse

    parser = argparse.ArgumentParser(description="Backfill weeks for survivor pool")
    parser.add_argument("--weeks", nargs="+", type=int, default=[1, 2],
                       help="Weeks to backfill (default: 1 2)")

    args = parser.parse_args()

    backfiller = BackfillProcessor()
    backfiller.run(args.weeks)