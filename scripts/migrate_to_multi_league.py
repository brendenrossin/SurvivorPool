#!/usr/bin/env python3
"""
Migration script to add multi-league support to the database.
This script is idempotent - safe to run multiple times.

Usage:
    python scripts/migrate_to_multi_league.py
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.database import SessionLocal, engine
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv()

def run_migration():
    """Execute the multi-league migration"""

    print("=" * 70)
    print("MULTI-LEAGUE MIGRATION - Adding league support to database")
    print("=" * 70)
    print()

    # Read migration SQL file
    migration_file = Path(__file__).parent.parent / "db" / "migrations" / "001_add_multi_league_support.sql"

    if not migration_file.exists():
        print(f"❌ Migration file not found: {migration_file}")
        return False

    print(f"📄 Reading migration from: {migration_file}")
    with open(migration_file, 'r') as f:
        migration_sql = f.read()

    # Connect to database
    db = SessionLocal()

    try:
        print("🔄 Executing migration...")
        print()

        # Execute migration in a transaction
        db.execute(text(migration_sql))

        # Update default league with values from environment
        google_sheet_id = os.getenv('GOOGLE_SHEETS_SPREADSHEET_ID')
        commissioner_email = os.getenv('COMMISSIONER_EMAIL', 'admin@example.com')

        print("📝 Updating default league with environment values...")
        db.execute(text("""
            UPDATE leagues
            SET
                google_sheet_id = :sheet_id,
                commissioner_email = :email
            WHERE league_id = 1
        """), {
            'sheet_id': google_sheet_id,
            'email': commissioner_email
        })

        db.commit()

        print("✅ Migration executed successfully!")
        print()

        # Verify migration
        print("🔍 Verifying migration...")

        # Check leagues table
        result = db.execute(text("SELECT COUNT(*) FROM leagues"))
        league_count = result.scalar()
        print(f"  ✓ Leagues table created: {league_count} league(s)")

        # Check players have league_id
        result = db.execute(text("SELECT COUNT(*) FROM players WHERE league_id IS NOT NULL"))
        players_with_league = result.scalar()
        print(f"  ✓ Players migrated: {players_with_league} player(s) with league_id")

        # Check picks have league_id
        result = db.execute(text("SELECT COUNT(*) FROM picks WHERE league_id IS NOT NULL"))
        picks_with_league = result.scalar()
        print(f"  ✓ Picks migrated: {picks_with_league} pick(s) with league_id")

        # Check new tables
        result = db.execute(text("SELECT COUNT(*) FROM users"))
        users_count = result.scalar()
        print(f"  ✓ Users table created: {users_count} user(s)")

        print()
        print("=" * 70)
        print("✨ MIGRATION COMPLETE!")
        print("=" * 70)
        print()
        print("📊 Default League Details:")

        # Show default league info
        result = db.execute(text("""
            SELECT
                league_id,
                league_name,
                league_slug,
                pick_source,
                season,
                commissioner_email,
                invite_code
            FROM leagues
            WHERE league_id = 1
        """))

        league = result.fetchone()
        if league:
            print(f"  League ID: {league[0]}")
            print(f"  Name: {league[1]}")
            print(f"  Slug: {league[2]}")
            print(f"  Pick Source: {league[3]}")
            print(f"  Season: {league[4]}")
            print(f"  Commissioner: {league[5]}")
            print(f"  Invite Code: {league[6]}")

        print()
        print("🎯 Next Steps:")
        print("  1. Update api/models.py to include new League model")
        print("  2. Update all queries to filter by league_id")
        print("  3. Test that existing dashboard still works")
        print("  4. Build league creation and management UI")
        print()

        return True

    except Exception as e:
        db.rollback()
        print(f"❌ Migration failed: {e}")
        print()
        print("💡 Common issues:")
        print("  - Tables might already exist (safe to ignore)")
        print("  - Check DATABASE_URL is correct")
        print("  - Ensure you have write permissions")
        return False

    finally:
        db.close()

def rollback_migration():
    """Rollback the migration (for testing purposes)"""

    print("=" * 70)
    print("⚠️  ROLLBACK MIGRATION - Removing multi-league support")
    print("=" * 70)
    print()

    db = SessionLocal()

    try:
        print("🔄 Rolling back migration...")

        # Drop new tables
        db.execute(text("DROP TABLE IF EXISTS league_commissioners CASCADE"))
        db.execute(text("DROP TABLE IF EXISTS user_players CASCADE"))
        db.execute(text("DROP TABLE IF EXISTS users CASCADE"))
        db.execute(text("DROP TABLE IF EXISTS leagues CASCADE"))

        # Remove league_id columns
        db.execute(text("ALTER TABLE picks DROP COLUMN IF EXISTS league_id"))
        db.execute(text("ALTER TABLE players DROP COLUMN IF EXISTS league_id"))

        db.commit()

        print("✅ Rollback complete!")
        print()

    except Exception as e:
        db.rollback()
        print(f"❌ Rollback failed: {e}")

    finally:
        db.close()

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Multi-league migration script")
    parser.add_argument("--rollback", action="store_true", help="Rollback the migration")
    args = parser.parse_args()

    if args.rollback:
        confirm = input("⚠️  Are you sure you want to rollback? This will delete league data. (yes/no): ")
        if confirm.lower() == "yes":
            rollback_migration()
        else:
            print("Rollback cancelled.")
    else:
        run_migration()
