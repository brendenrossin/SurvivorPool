#!/usr/bin/env python3
"""
Railway Database Migration - Add Odds Columns
Run this ONCE after deploying to Railway to add the new columns
"""

import os
import sys
from dotenv import load_dotenv
from sqlalchemy import text, create_engine

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

def apply_railway_migration():
    """Apply the odds columns migration to Railway PostgreSQL"""

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ No DATABASE_URL found. Make sure you're connected to Railway.")
        return False

    print(f"🔧 Applying odds migration to Railway database...")
    print(f"🔗 Database URL: {database_url[:50]}...")

    try:
        # Create engine directly for Railway
        engine = create_engine(database_url)

        with engine.begin() as conn:

            # Add point_spread column
            try:
                conn.execute(text("ALTER TABLE games ADD COLUMN point_spread REAL"))
                print("✅ Added point_spread column")
            except Exception as e:
                if "already exists" in str(e) or "duplicate column" in str(e).lower():
                    print("ℹ️  point_spread column already exists")
                else:
                    print(f"⚠️  Error adding point_spread: {e}")

            # Add favorite_team column
            try:
                conn.execute(text("ALTER TABLE games ADD COLUMN favorite_team VARCHAR(50)"))
                print("✅ Added favorite_team column")
            except Exception as e:
                if "already exists" in str(e) or "duplicate column" in str(e).lower():
                    print("ℹ️  favorite_team column already exists")
                else:
                    print(f"⚠️  Error adding favorite_team: {e}")

            # Add indexes for performance
            try:
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_games_point_spread ON games (point_spread)"))
                print("✅ Added point_spread index")
            except Exception as e:
                print(f"⚠️  Error adding point_spread index: {e}")

            try:
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_games_favorite_team ON games (favorite_team)"))
                print("✅ Added favorite_team index")
            except Exception as e:
                print(f"⚠️  Error adding favorite_team index: {e}")

        print("🎉 Railway migration completed successfully!")

        # Verify the migration (PostgreSQL only) - separate connection for verification
        if "postgresql" in database_url.lower():
            with engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_name = 'games'
                    AND column_name IN ('point_spread', 'favorite_team')
                    ORDER BY column_name
                """))

                print("\n📋 Verified columns:")
                for row in result:
                    print(f"   {row.column_name}: {row.data_type} (nullable: {row.is_nullable})")
        else:
            print("\n📋 Column verification skipped (not PostgreSQL)")

        return True

    except Exception as e:
        print(f"❌ Railway migration failed: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Railway Database Migration for Odds Integration")
    print("=" * 60)

    success = apply_railway_migration()

    if success:
        print("\n✅ Migration successful! Your Railway app should now work with odds.")
        print("🎯 Next steps:")
        print("   1. Add THE_ODDS_API_KEY to Railway environment variables")
        print("   2. Configure cron jobs in Railway service settings")
        print("   3. Run python jobs/update_scores.py --fetch-odds to populate odds")
    else:
        print("\n❌ Migration failed. Check the errors above.")

    sys.exit(0 if success else 1)