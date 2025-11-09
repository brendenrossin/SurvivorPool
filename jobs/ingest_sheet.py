#!/usr/bin/env python3
"""
Ingest survivor picks from Google Sheets using service account credentials
This uses the EXACT same logic as ingest_personal_sheets.py (OAuth version)
Only difference: uses service account client instead of OAuth client
"""

import os
import sys
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.database import SessionLocal
from api.models import Player, Pick, PickResult
from api.sheets import GoogleSheetsClient
from dotenv import load_dotenv
from sqlalchemy import text

def parse_picks_data(raw_data):
    """Parse raw Google Sheets data into player picks

    Converts raw sheet rows into: {player_name: {week: team}}
    This matches the OAuth version's data structure exactly
    """
    print("🧮 Parsing Google Sheets data...")

    if not raw_data or len(raw_data) < 2:
        print("⚠️ No data to parse")
        return {}

    players_data = {}

    # First row is header
    header = raw_data[0]
    rows = raw_data[1:]

    # Find week columns
    week_columns = []
    for i, col_name in enumerate(header):
        if col_name and col_name.startswith('Week ') and col_name.replace('Week ', '').isdigit():
            week_num = int(col_name.replace('Week ', ''))
            week_columns.append((i, week_num))

    print(f"   Found {len(week_columns)} week columns")

    # Parse each row
    for row_idx, row in enumerate(rows):
        try:
            # Get player name (first column)
            if not row or len(row) == 0:
                continue

            name = row[0].strip() if row[0] else ''
            if not name:
                continue

            # Initialize player if not seen
            if name not in players_data:
                players_data[name] = {}

            # Parse weekly picks
            for col_idx, week_num in week_columns:
                if col_idx < len(row):
                    team = row[col_idx].strip().upper() if row[col_idx] else ''
                    if team and team != '':
                        players_data[name][week_num] = team

        except Exception as e:
            print(f"⚠️ Error parsing row {row_idx + 2}: {e}")
            continue

    print(f"✅ Parsed {len(players_data)} players from Google Sheets")
    return players_data

def ingest_players_and_picks(players_data):
    """Insert/update players and picks in database

    EXACT same logic as ingest_personal_sheets.py
    """
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
                        source="google_sheets"
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
    print("📊 Service Account Google Sheets Ingestion")
    print("=" * 50)

    # Load environment
    load_dotenv()

    # Create client and get data
    client = GoogleSheetsClient()
    raw_data = client.get_picks_data()

    if not raw_data:
        print("⚠️ No data retrieved from Google Sheets (check service account)")
        return True  # Don't fail deployment, just skip ingestion

    # Parse the data
    players_data = parse_picks_data(raw_data)

    if not players_data:
        print("⚠️ No valid picks data parsed")
        return True  # Don't fail deployment

    # Ingest into database
    success = ingest_players_and_picks(players_data)

    if success:
        print("\n🎉 Service account ingestion successful!")
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
        print("\n❌ Service account ingestion failed")

    return success

if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)
