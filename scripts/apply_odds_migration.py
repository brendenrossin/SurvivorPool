#!/usr/bin/env python3
"""
Apply database migration to add odds columns
"""

import os
import sys
from dotenv import load_dotenv
from sqlalchemy import text

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.database import SessionLocal

load_dotenv()

def apply_migration():
    """Apply the odds columns migration"""
    db = SessionLocal()

    try:
        print("🔧 Applying odds columns migration...")

        # Add point_spread column
        try:
            db.execute(text("ALTER TABLE games ADD COLUMN point_spread REAL"))
            print("✅ Added point_spread column")
        except Exception as e:
            if "already exists" in str(e) or "duplicate column" in str(e):
                print("ℹ️  point_spread column already exists")
            else:
                print(f"⚠️  Error adding point_spread: {e}")

        # Add favorite_team column
        try:
            db.execute(text("ALTER TABLE games ADD COLUMN favorite_team VARCHAR(10)"))
            print("✅ Added favorite_team column")
        except Exception as e:
            if "already exists" in str(e) or "duplicate column" in str(e):
                print("ℹ️  favorite_team column already exists")
            else:
                print(f"⚠️  Error adding favorite_team: {e}")

        # Add indexes for performance
        try:
            db.execute(text("CREATE INDEX IF NOT EXISTS idx_games_point_spread ON games (point_spread)"))
            print("✅ Added point_spread index")
        except Exception as e:
            print(f"⚠️  Error adding point_spread index: {e}")

        try:
            db.execute(text("CREATE INDEX IF NOT EXISTS idx_games_favorite_team ON games (favorite_team)"))
            print("✅ Added favorite_team index")
        except Exception as e:
            print(f"⚠️  Error adding favorite_team index: {e}")

        db.commit()
        print("🎉 Migration completed successfully!")

        # Verify the migration
        result = db.execute(text("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'games'
            AND column_name IN ('point_spread', 'favorite_team')
            ORDER BY column_name
        """))

        print("\n📋 Verified columns:")
        for row in result:
            print(f"   {row.column_name}: {row.data_type} (nullable: {row.is_nullable})")

    except Exception as e:
        db.rollback()
        print(f"❌ Migration failed: {e}")
        return False
    finally:
        db.close()

    return True

if __name__ == "__main__":
    apply_migration()