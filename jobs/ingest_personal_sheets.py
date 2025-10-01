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

            # Parse weekly picks dynamically - find all Week X columns
            week_columns = [key for key in parsed.keys() if key.startswith('Week ') and key.replace('Week ', '').isdigit()]
            for week_col in week_columns:
                week_num = int(week_col.replace('Week ', ''))
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

        # Clear existing picks and players - we'll recalculate pick_results from current games
        print("🧹 Clearing existing pick and player data...")

        # Delete picks and players (this cascades to pick_results)
        db.execute(text("DELETE FROM picks WHERE season = :season"), {"season": season})
        db.execute(text("DELETE FROM players"))  # Clear all players to avoid orphans
        db.commit()
        print("✅ Existing data cleared")

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

        # Re-calculate ALL elimination results using shared helper
        # This ensures consistency with app startup and cron jobs
        print("🔄 Re-calculating elimination results from current game data...")
        try:
            # Use SHARED HELPER to ensure consistency
            from jobs.update_scores import ScoreUpdater

            updater = ScoreUpdater()

            # Process ALL elimination logic (picks, stuck games, missing picks)
            elimination_results = updater.process_all_eliminations(db)

            print(f"   ✅ Elimination processing complete:")
            print(f"      - Pick results: {elimination_results['picks_updated']}")
            print(f"      - Stuck games fixed: {elimination_results['stuck_games_fixed']}")
            print(f"      - Missing pick eliminations: {elimination_results['missing_pick_eliminations']}")
        except Exception as e:
            print(f"   ⚠️ Failed to process eliminations: {e}")
            import traceback
            traceback.print_exc()

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