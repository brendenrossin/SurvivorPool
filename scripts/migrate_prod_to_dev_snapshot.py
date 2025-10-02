#!/usr/bin/env python3
"""
One-time migration: Copy production data to dev League 1 as a snapshot
This is a READ-ONLY operation on production (100% safe)
"""

import os
import sys
from sqlalchemy import create_engine, text

def migrate_production_to_dev_snapshot():
    """
    Migrate production data to dev database League 1 as a one-time snapshot.

    Production DB: READ ONLY (no writes)
    Dev DB: WRITE (inserts only)
    """

    # Get database URLs
    prod_url = os.getenv('DATABASE_PUBLIC_URL')
    dev_url = 'postgresql://postgres:***REMOVED***@yamanote.proxy.rlwy.net:35600/railway'

    if not prod_url:
        print("ERROR: DATABASE_PUBLIC_URL not set")
        return False

    target_league_id = 1  # Rossin Family Survivor Pool 2025

    print("=" * 80)
    print("PRODUCTION → DEV MIGRATION (ONE-TIME SNAPSHOT)")
    print("=" * 80)
    print(f"Production DB: {prod_url[:50]}... (READ ONLY)")
    print(f"Dev DB: {dev_url[:50]}... (WRITE)")
    print(f"Target League ID: {target_league_id}")
    print("=" * 80)

    # Connect to both databases
    prod_engine = create_engine(prod_url)
    dev_engine = create_engine(dev_url)

    try:
        # Step 1: Read production data (READ ONLY)
        print("\n[1/4] Reading production data (READ ONLY)...")

        with prod_engine.connect() as prod_conn:
            # Read players (production doesn't have created_at)
            players = prod_conn.execute(text("""
                SELECT player_id, display_name
                FROM players
                ORDER BY player_id
            """)).fetchall()

            # Read picks (production has picked_at, not created_at)
            picks = prod_conn.execute(text("""
                SELECT pick_id, player_id, season, week, team_abbr, picked_at
                FROM picks
                ORDER BY pick_id
            """)).fetchall()

            # Read pick_results (production doesn't have pick_result_id or updated_at)
            pick_results = prod_conn.execute(text("""
                SELECT pick_id, game_id, is_locked, is_valid, survived
                FROM pick_results
                ORDER BY pick_id
            """)).fetchall()

            # Read games (needed for pick_results foreign key) - only columns that exist in production
            games = prod_conn.execute(text("""
                SELECT game_id, season, week, kickoff, home_team, away_team,
                       status, home_score, away_score, winner_abbr,
                       point_spread, favorite_team
                FROM games
                WHERE season = 2025
                ORDER BY game_id
            """)).fetchall()

        print(f"  ✓ Read {len(players)} players")
        print(f"  ✓ Read {len(picks)} picks")
        print(f"  ✓ Read {len(pick_results)} pick_results")
        print(f"  ✓ Read {len(games)} games")

        # Step 2: Check dev League 1 is empty
        print(f"\n[2/4] Checking dev League {target_league_id} status...")

        with dev_engine.connect() as dev_conn:
            existing_players = dev_conn.execute(text(
                "SELECT COUNT(*) FROM players WHERE league_id = :lid"
            ), {'lid': target_league_id}).scalar()

            existing_picks = dev_conn.execute(text(
                "SELECT COUNT(*) FROM picks WHERE league_id = :lid"
            ), {'lid': target_league_id}).scalar()

        if existing_players > 0 or existing_picks > 0:
            print(f"  ⚠️  WARNING: League {target_league_id} already has data:")
            print(f"     - {existing_players} players")
            print(f"     - {existing_picks} picks")
            response = input("  Clear existing data and continue? (yes/no): ")
            if response.lower() != 'yes':
                print("  ❌ Migration cancelled")
                return False

            # Clear existing data
            print(f"  🗑️  Clearing existing data from League {target_league_id}...")
            with dev_engine.begin() as dev_conn:
                dev_conn.execute(text("DELETE FROM pick_results WHERE pick_id IN (SELECT pick_id FROM picks WHERE league_id = :lid)"), {'lid': target_league_id})
                dev_conn.execute(text("DELETE FROM picks WHERE league_id = :lid"), {'lid': target_league_id})
                dev_conn.execute(text("DELETE FROM players WHERE league_id = :lid"), {'lid': target_league_id})
                dev_conn.execute(text("DELETE FROM games WHERE season = 2025"))  # Clear 2025 games
            print("  ✓ Cleared existing data")
        else:
            print(f"  ✓ League {target_league_id} is empty, ready for migration")

        # Step 3: Insert transformed data into dev (BULK INSERTS for speed)
        print(f"\n[3/4] Inserting data into dev League {target_league_id} (WRITE)...")

        with dev_engine.begin() as dev_conn:
            # Bulk insert players
            if players:
                player_values = ', '.join([
                    f"({p[0]}, {target_league_id}, '{p[1].replace(chr(39), chr(39)+chr(39))}')"
                    for p in players
                ])
                dev_conn.execute(text(f"""
                    INSERT INTO players (player_id, league_id, display_name)
                    VALUES {player_values}
                """))
                print(f"  ✓ Inserted {len(players)} players")

            # Bulk insert picks
            if picks:
                pick_values = ', '.join([
                    f"({p[0]}, {p[1]}, {target_league_id}, {p[2]}, {p[3]}, "
                    f"{'NULL' if p[4] is None else chr(39) + p[4] + chr(39)})"
                    for p in picks
                ])
                dev_conn.execute(text(f"""
                    INSERT INTO picks (pick_id, player_id, league_id, season, week, team_abbr)
                    VALUES {pick_values}
                """))
                print(f"  ✓ Inserted {len(picks)} picks")

            # Bulk insert games
            if games:
                sq = chr(39)  # single quote
                game_values = ', '.join([
                    f"({sq}{g[0]}{sq}, {g[1]}, {g[2]}, "
                    f"{'NULL' if g[3] is None else sq + str(g[3]) + sq}, "
                    f"{sq}{g[4]}{sq}, {sq}{g[5]}{sq}, "
                    f"{'NULL' if g[6] is None else sq + g[6] + sq}, "
                    f"{g[7] if g[7] is not None else 'NULL'}, "
                    f"{g[8] if g[8] is not None else 'NULL'}, "
                    f"{'NULL' if g[9] is None else sq + g[9] + sq}, "
                    f"{g[10] if g[10] is not None else 'NULL'}, "
                    f"{'NULL' if g[11] is None else sq + g[11] + sq})"
                    for g in games
                ])
                dev_conn.execute(text(f"""
                    INSERT INTO games (game_id, season, week, kickoff, home_team, away_team,
                                      status, home_score, away_score, winner_abbr,
                                      point_spread, favorite_team)
                    VALUES {game_values}
                    ON CONFLICT (game_id) DO NOTHING
                """))
                print(f"  ✓ Inserted {len(games)} games")

            # Bulk insert pick_results
            if pick_results:
                sq = chr(39)  # single quote
                pr_values = ', '.join([
                    f"({pr[0]}, "
                    f"{'NULL' if pr[1] is None else sq + pr[1] + sq}, "
                    f"{'true' if pr[2] else 'false'}, "
                    f"{'true' if pr[3] else 'false'}, "
                    f"{'NULL' if pr[4] is None else ('true' if pr[4] else 'false')})"
                    for pr in pick_results
                ])
                dev_conn.execute(text(f"""
                    INSERT INTO pick_results (pick_id, game_id, is_locked, is_valid, survived)
                    VALUES {pr_values}
                """))
                print(f"  ✓ Inserted {len(pick_results)} pick_results")

        # Step 4: Verify migration
        print(f"\n[4/4] Verifying migration...")

        with dev_engine.connect() as dev_conn:
            final_players = dev_conn.execute(text(
                "SELECT COUNT(*) FROM players WHERE league_id = :lid"
            ), {'lid': target_league_id}).scalar()

            final_picks = dev_conn.execute(text(
                "SELECT COUNT(*) FROM picks WHERE league_id = :lid"
            ), {'lid': target_league_id}).scalar()

            final_eliminations = dev_conn.execute(text("""
                SELECT COUNT(DISTINCT p.player_id)
                FROM picks p
                JOIN pick_results pr ON p.pick_id = pr.pick_id
                WHERE p.league_id = :lid AND pr.survived = false
            """), {'lid': target_league_id}).scalar()

        print(f"  ✓ League {target_league_id} now has:")
        print(f"    - {final_players} players")
        print(f"    - {final_picks} picks")
        print(f"    - {final_eliminations} eliminations")

        print("\n" + "=" * 80)
        print("✅ MIGRATION COMPLETE!")
        print("=" * 80)
        print(f"Production data snapshot copied to dev League {target_league_id}")
        print("Production database was NOT modified (read-only operation)")
        print(f"\nView dev dashboard: https://web-dev-dev.up.railway.app/?league=rossin-family-2025")

        return True

    except Exception as e:
        print(f"\n❌ ERROR during migration: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        prod_engine.dispose()
        dev_engine.dispose()

if __name__ == '__main__':
    success = migrate_production_to_dev_snapshot()
    sys.exit(0 if success else 1)
