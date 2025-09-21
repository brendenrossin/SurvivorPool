#!/usr/bin/env python3
"""
Scores update job - fetches NFL scores and updates database
"""

import os
import sys
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import and_

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.database import SessionLocal
from api.models import Game, Pick, PickResult, JobMeta
from api.score_providers import get_score_provider
from api.odds_providers import get_odds_provider
from dotenv import load_dotenv

load_dotenv()

class ScoreUpdater:
    def __init__(self):
        provider_name = os.getenv("SCORES_PROVIDER", "espn")
        self.score_provider = get_score_provider(provider_name)
        odds_provider_name = os.getenv("ODDS_PROVIDER", "the_odds_api")
        self.odds_provider = get_odds_provider(odds_provider_name)
        self.season = int(os.getenv("NFL_SEASON", 2025))

    def run(self, fetch_odds=False):
        """Main score update process"""
        db = SessionLocal()
        try:
            print(f"Starting score update at {datetime.now()}")

            # Update job meta
            self.update_job_meta(db, "update_scores", "running", "Starting score update")

            # Get current week
            current_week = self.score_provider.get_current_week(self.season)
            print(f"Updating scores for Season {self.season}, Week {current_week}")

            # Fetch games and scores
            games = self.score_provider.get_schedule_and_scores(self.season, current_week)

            # Optionally fetch betting odds (for backwards compatibility or manual runs)
            if fetch_odds:
                print("🎰 Fetching odds along with scores...")
                odds_data = self.odds_provider.get_nfl_odds(self.season, current_week)
                games_with_odds = self.merge_odds_with_games(games, odds_data)
            else:
                games_with_odds = games

            # Update games in database
            games_updated = self.upsert_games(db, games_with_odds)

            # Update pick results
            picks_updated = self.update_pick_results(db, current_week)

            db.commit()

            message = f"Updated {games_updated} games, {picks_updated} pick results for week {current_week}"
            self.update_job_meta(db, "update_scores", "success", message)

            print(f"Score update completed: {message}")

        except Exception as e:
            db.rollback()
            error_msg = f"Error during score update: {str(e)}"
            self.update_job_meta(db, "update_scores", "error", error_msg)
            print(error_msg)
            print("⚠️  Continuing despite score update error")
            return False  # Don't raise, just return False
        finally:
            db.close()

    def merge_odds_with_games(self, games: list, odds_data: dict) -> list:
        """Merge betting odds with game data"""
        games_with_odds = []

        for game in games:
            # Create a key to match with odds data
            game_key = f"{game.away_team}_at_{game.home_team}"

            # Check if we have odds for this game
            if game_key in odds_data:
                odds = odds_data[game_key]
                # Update game with odds
                game.point_spread = odds.get("point_spread")
                game.favorite_team = odds.get("favorite_team")
                print(f"🎰 Added odds: {game.away_team} @ {game.home_team} - {odds.get('favorite_team')} -{odds.get('point_spread')}")

            games_with_odds.append(game)

        return games_with_odds

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
                # Update odds if available
                if game_data.point_spread is not None:
                    existing_game.point_spread = game_data.point_spread
                if game_data.favorite_team is not None:
                    existing_game.favorite_team = game_data.favorite_team
                updated_count += 1
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
                    winner_abbr=game_data.winner_abbr,
                    point_spread=game_data.point_spread,
                    favorite_team=game_data.favorite_team
                )
                db.add(new_game)
                updated_count += 1

        return updated_count

    def update_pick_results(self, db: Session, week: int) -> int:
        """Update pick results for games that have concluded"""
        updated_count = 0

        # Get all picks for the current week
        picks = db.query(Pick).filter(
            and_(
                Pick.season == self.season,
                Pick.week == week,
                Pick.team_abbr.isnot(None)
            )
        ).all()

        for pick in picks:
            # Find the game for this pick
            game = db.query(Game).filter(
                and_(
                    Game.season == pick.season,
                    Game.week == pick.week,
                    ((Game.home_team == pick.team_abbr) | (Game.away_team == pick.team_abbr))
                )
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
            if pick_result.game_id != game.game_id:
                pick_result.game_id = game.game_id
                updated_count += 1

            # Check if game has started (locking logic)
            now = datetime.now(timezone.utc)
            # Convert game.kickoff to UTC if it's naive (assume UTC)
            game_kickoff = game.kickoff.replace(tzinfo=timezone.utc) if game.kickoff.tzinfo is None else game.kickoff
            if now >= game_kickoff and not pick_result.is_locked:
                pick_result.is_locked = True
                updated_count += 1

            # Update survival status if game is complete
            # Check if game is finished - either marked as final OR has scores and kickoff was >4 hours ago
            is_game_complete = False
            if game.status == "final":
                is_game_complete = True
            elif (game.home_score is not None and game.away_score is not None and
                  game.kickoff is not None):
                # Game has scores - check if kickoff was more than 4 hours ago
                hours_since_kickoff = (now - game_kickoff).total_seconds() / 3600
                is_game_complete = hours_since_kickoff > 4

            if is_game_complete:
                # Mark game as final if it's complete but still shows as 'in'
                if game.status != "final":
                    game.status = "final"
                    updated_count += 1

                # Determine winner if not already set
                if game.winner_abbr is None and game.home_score is not None and game.away_score is not None:
                    if game.home_score > game.away_score:
                        game.winner_abbr = game.home_team
                    elif game.away_score > game.home_score:
                        game.winner_abbr = game.away_team
                    # Ties leave winner_abbr as None
                    updated_count += 1

                # Update pick survival status
                if game.winner_abbr is not None:
                    old_survived = pick_result.survived
                    pick_result.survived = (pick.team_abbr == game.winner_abbr)

                    if old_survived != pick_result.survived:
                        updated_count += 1

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
    import argparse

    parser = argparse.ArgumentParser(description="Update NFL scores")
    parser.add_argument("--fetch-odds", action="store_true",
                       help="Also fetch betting odds (uses API credits)")
    args = parser.parse_args()

    updater = ScoreUpdater()
    updater.run(fetch_odds=args.fetch_odds)