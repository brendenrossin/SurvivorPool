#!/usr/bin/env python3
"""
Initialize database for Railway deployment
Run this once after your Railway database is provisioned
"""

import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

def init_railway_db():
    """Initialize Railway database"""
    load_dotenv()

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ DATABASE_URL not found!")
        print("   Make sure Railway has provisioned your database")
        return False

    try:
        print("🚂 Initializing Railway database...")
        engine = create_engine(database_url)

        # Read and execute migrations
        with open("db/migrations.sql", "r") as f:
            sql_commands = f.read()

        with engine.begin() as conn:
            # Remove comments and split by semicolon
            lines = []
            for line in sql_commands.split('\n'):
                line = line.strip()
                # Skip comment-only lines
                if line.startswith('--') or not line:
                    continue
                # Remove inline comments
                if '--' in line:
                    line = line.split('--')[0].strip()
                if line:
                    lines.append(line)

            # Join lines and split by semicolon
            clean_sql = ' '.join(lines)
            commands = [cmd.strip() for cmd in clean_sql.split(';') if cmd.strip()]

            for i, command in enumerate(commands, 1):
                print(f"   Executing command {i}/{len(commands)}...")
                print(f"   Command: {command[:50]}..." if len(command) > 50 else f"   Command: {command}")
                conn.execute(text(command))

        print("✅ Railway database initialized!")

        # Apply odds integration migration
        print("🎰 Applying odds integration migration...")

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

        print("🎉 Odds integration migration completed!")
        return True

    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        return False

if __name__ == "__main__":
    init_railway_db()