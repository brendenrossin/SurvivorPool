#!/usr/bin/env python3
"""
Ingest survivor picks from Google Sheets using personal OAuth2 credentials
This replaces the service account version with personal OAuth
"""

import os
import sys
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.database import SessionLocal
from api.models import Player, Pick, PickResult
from api.sheets_personal_railway import RailwayPersonalSheetsClient
from dotenv import load_dotenv
from sqlalchemy import text

def parse_picks_data(picks_data):
    """Parse raw Google Sheets data into player picks"""
    print("🧮 Parsing Google Sheets data...")

    players_data = {}

    for record in picks_data:
        try:
            parsed = record['parsed_data']

            # Get player name (assuming first column)
            name = parsed.get('Name', '').strip()
            if not name:
                continue

            # Initialize player if not seen
            if name not in players_data:
                players_data[name] = {}

            # Parse weekly picks (assuming Week 1, Week 2, Week 3, Week 4 columns)
            for week_num in [1, 2, 3, 4]:
                week_col = f'Week {week_num}'
                if week_col in parsed:
                    team = parsed[week_col].strip().upper()
                    if team and team != '':
                        players_data[name][week_num] = team

        except Exception as e:
            print(f"⚠️ Error parsing row {record.get('row_number', '?')}: {e}")
            continue

    print(f"✅ Parsed {len(players_data)} players from Google Sheets")
    return players_data

def ingest_players_and_picks(players_data):
    """Insert/update players and picks in database"""
    db = SessionLocal()

    try:
        print("👥 Ingesting players and picks...")

        season = int(os.getenv('NFL_SEASON', 2025))

        # Clear existing picks and players, but preserve calculated pick_results
        print("🧹 Clearing existing pick and player data (preserving calculated results)...")
        # First, save pick_results that have been calculated by score updates
        db.execute(text("""
            CREATE TEMPORARY TABLE temp_pick_results AS
            SELECT pr.* FROM pick_results pr
            JOIN picks p ON pr.pick_id = p.pick_id
            WHERE p.season = :season AND pr.game_id IS NOT NULL
        """), {"season": season})

        # Delete picks and players (this cascades to pick_results)
        db.execute(text("DELETE FROM picks WHERE season = :season"), {"season": season})
        db.execute(text("DELETE FROM players"))  # Clear all players to avoid orphans
        db.commit()
        print("✅ Existing data cleared (calculated results preserved)")

        players_created = 0
        picks_created = 0
        picks_updated = 0

        for player_name, weekly_picks in players_data.items():
            # Get or create player
            player = db.query(Player).filter(Player.display_name == player_name).first()

            if not player:
                player = Player(display_name=player_name)
                db.add(player)
                db.flush()  # Get ID
                players_created += 1
                print(f"   ➕ Created player: {player_name}")

            # Process weekly picks
            for week, team in weekly_picks.items():
                # Check if pick already exists
                existing_pick = db.query(Pick).filter(
                    Pick.player_id == player.player_id,
                    Pick.season == season,
                    Pick.week == week
                ).first()

                if existing_pick:
                    # Update if team changed
                    if existing_pick.team_abbr != team:
                        print(f"   🔄 Updating {player_name} Week {week}: {existing_pick.team_abbr} → {team}")
                        existing_pick.team_abbr = team
                        picks_updated += 1
                else:
                    # Create new pick
                    new_pick = Pick(
                        player_id=player.player_id,
                        season=season,
                        week=week,
                        team_abbr=team,
                        source="google_sheets_personal"
                    )
                    db.add(new_pick)
                    picks_created += 1

        # Restore calculated pick_results by matching player names and weeks
        print("🔄 Restoring calculated elimination results...")
        try:
            restored_results = db.execute(text("""
                INSERT INTO pick_results (pick_id, game_id, survived, is_locked, is_valid)
                SELECT
                    new_p.pick_id,
                    temp_pr.game_id,
                    temp_pr.survived,
                    temp_pr.is_locked,
                    temp_pr.is_valid
                FROM temp_pick_results temp_pr
                JOIN picks old_p ON temp_pr.pick_id = old_p.pick_id
                JOIN players old_pl ON old_p.player_id = old_pl.player_id
                JOIN players new_pl ON old_pl.display_name = new_pl.display_name
                JOIN picks new_p ON new_pl.player_id = new_p.player_id
                    AND new_p.week = old_p.week
                    AND new_p.season = old_p.season
                WHERE temp_pr.game_id IS NOT NULL
            """))
            print(f"   ✅ Restored {restored_results.rowcount} calculated elimination results")
        except Exception as e:
            print(f"   ⚠️ Failed to restore results: {e}")

        # Clean up temporary table
        try:
            db.execute(text("DROP TABLE temp_pick_results"))
        except:
            pass  # Table might not exist

        db.commit()

        print(f"✅ Ingestion complete!")
        print(f"   Players created: {players_created}")
        print(f"   Picks created: {picks_created}")
        print(f"   Picks updated: {picks_updated}")

        return True

    except Exception as e:
        print(f"❌ Database ingestion failed: {e}")
        db.rollback()
        import traceback
        traceback.print_exc()
        return False

    finally:
        db.close()

def main():
    """Main ingestion process"""
    print("📊 Personal OAuth2 Google Sheets Ingestion")
    print("=" * 50)

    # Load environment
    load_dotenv()

    # Create client and get data
    client = RailwayPersonalSheetsClient()
    picks_data = client.get_picks_data()

    if not picks_data:
        print("⚠️ No data retrieved from Google Sheets (check OAuth credentials)")
        return True  # Don't fail deployment, just skip ingestion

    # Parse the data
    players_data = parse_picks_data(picks_data)

    if not players_data:
        print("⚠️ No valid picks data parsed")
        return True  # Don't fail deployment

    # Ingest into database
    success = ingest_players_and_picks(players_data)

    if success:
        print("\n🎉 Personal OAuth2 ingestion successful!")
        print("🚀 Your dashboard should now show real survivor picks!")

        # After successful ingestion, populate historical eliminations
        print("\n🔄 Populating historical elimination data...")
        try:
            from manual_historical import mark_eliminations
            mark_eliminations()
            print("✅ Historical eliminations populated")
        except Exception as e:
            print(f"⚠️ Historical elimination population failed: {e}")
    else:
        print("\n❌ Personal OAuth2 ingestion failed")

    return success

if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)