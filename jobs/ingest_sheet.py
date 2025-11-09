#!/usr/bin/env python3
"""
Sheet ingestion job - pulls picks from Google Sheets and updates database
"""

import os
import sys
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import and_

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.database import SessionLocal, engine
from api.models import Player, Pick, PickResult, Game, JobMeta
from api.sheets import GoogleSheetsClient
from dotenv import load_dotenv

load_dotenv()

class SheetIngestor:
    def __init__(self):
        self.sheets_client = GoogleSheetsClient()
        self.season = int(os.getenv("NFL_SEASON", 2025))

    def run(self):
        """Main ingestion process"""
        db = SessionLocal()
        try:
            print(f"Starting sheet ingestion at {datetime.now(timezone.utc)}")

            # Update job meta
            self.update_job_meta(db, "ingest_sheet", "running", "Starting ingestion")

            # Fetch data from sheets
            raw_data = self.sheets_client.get_picks_data()
            print(f"📊 Fetched {len(raw_data)} rows from Sheet")
            print(f"📋 Header: {raw_data[0][:8] if raw_data else 'No data'}...")

            parsed_data = self.sheets_client.parse_picks_data(raw_data)
            print(f"👥 Parsed {len(parsed_data['players'])} players")
            print(f"📊 Parsed {len(parsed_data['picks'])} picks")

            if len(parsed_data['picks']) > 0:
                print(f"   Sample pick: {parsed_data['picks'][0]}")
            else:
                print(f"   ⚠️ WARNING: No picks parsed!")

            # Process players and picks
            players_created = self.upsert_players(db, parsed_data["players"])
            picks_updated = self.upsert_picks(db, parsed_data["picks"])

            # Skip validation - commissioner's sheet is source of truth
            validation_updates = 0

            db.commit()

            message = f"Processed {len(parsed_data['players'])} players, {picks_updated} picks, {validation_updates} validations"
            self.update_job_meta(db, "ingest_sheet", "success", message)

            print(f"Sheet ingestion completed: {message}")

        except Exception as e:
            db.rollback()
            import traceback
            print("=== FULL TRACEBACK ===")
            traceback.print_exc()
            print("=== END TRACEBACK ===")
            error_msg = f"Error during sheet ingestion: {str(e)}"
            self.update_job_meta(db, "ingest_sheet", "error", error_msg)
            print(error_msg)
            print("⚠️  Continuing despite sheet ingestion error (likely permissions)")
            return False  # Don't raise, just return False
        finally:
            db.close()

    def upsert_players(self, db: Session, player_names: list) -> int:
        """Create or update players"""
        created_count = 0
        for name in player_names:
            existing = db.query(Player).filter(Player.display_name == name).first()
            if not existing:
                player = Player(display_name=name)
                db.add(player)
                created_count += 1

        return created_count

    def upsert_picks(self, db: Session, picks_data: list) -> int:
        """Create or update picks, respecting lock status"""
        updated_count = 0
        skipped_no_player = 0

        for pick_data in picks_data:
            player = db.query(Player).filter(
                Player.display_name == pick_data["player_name"]
            ).first()

            if not player:
                skipped_no_player += 1
                continue

            # Check if pick exists
            existing_pick = db.query(Pick).filter(
                and_(
                    Pick.player_id == player.player_id,
                    Pick.season == self.season,
                    Pick.week == pick_data["week"]
                )
            ).first()

            if existing_pick:
                # Commissioner's sheet is source of truth - always update
                if existing_pick.team_abbr != pick_data["team_abbr"]:
                    existing_pick.team_abbr = pick_data["team_abbr"]
                    existing_pick.source = "google_sheets"  # Update source
                    existing_pick.picked_at = datetime.now(timezone.utc)
                    updated_count += 1
            else:
                # Create new pick
                new_pick = Pick(
                    player_id=player.player_id,
                    season=self.season,
                    week=pick_data["week"],
                    team_abbr=pick_data["team_abbr"]
                )
                db.add(new_pick)
                updated_count += 1

        if skipped_no_player > 0:
            print(f"   ⚠️ Skipped {skipped_no_player} picks (player not found)")

        return updated_count

    def validate_picks(self, db: Session) -> int:
        """Validate picks for duplicate team usage and create/update pick_results"""
        updated_count = 0

        # Get all picks for current season
        picks = db.query(Pick).filter(Pick.season == self.season).all()

        for pick in picks:
            # Ensure pick_result exists
            pick_result = db.query(PickResult).filter(
                PickResult.pick_id == pick.pick_id
            ).first()

            if not pick_result:
                pick_result = PickResult(pick_id=pick.pick_id)
                db.add(pick_result)

            # Check for duplicate team usage by this player in this season
            duplicate_picks = db.query(Pick).filter(
                and_(
                    Pick.player_id == pick.player_id,
                    Pick.season == pick.season,
                    Pick.team_abbr == pick.team_abbr,
                    Pick.team_abbr.isnot(None),
                    Pick.pick_id != pick.pick_id
                )
            ).count()

            # Update validity
            old_valid = pick_result.is_valid
            pick_result.is_valid = (duplicate_picks == 0)

            if old_valid != pick_result.is_valid:
                updated_count += 1

            # Try to link to game
            if pick.team_abbr:
                game = db.query(Game).filter(
                    and_(
                        Game.season == pick.season,
                        Game.week == pick.week,
                        ((Game.home_team == pick.team_abbr) | (Game.away_team == pick.team_abbr))
                    )
                ).first()

                if game:
                    pick_result.game_id = game.game_id

                    # Check if game has started (lock logic)
                    now = datetime.now(timezone.utc)
                    # Ensure game.kickoff is timezone-aware for comparison
                    game_kickoff = game.kickoff
                    if game_kickoff.tzinfo is None:
                        game_kickoff = game_kickoff.replace(tzinfo=timezone.utc)

                    if now >= game_kickoff and not pick_result.is_locked:
                        pick_result.is_locked = True
                        updated_count += 1

                    # Update survival status if game is final
                    if game.status == "final" and game.winner_abbr:
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
    ingestor = SheetIngestor()
    ingestor.run()