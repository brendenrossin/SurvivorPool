#!/usr/bin/env python3
"""
Database setup script - run this once to initialize your database
"""

import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

def setup_database():
    """Initialize database with schema"""
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        print("❌ DATABASE_URL not found in environment variables!")
        print("   Please set DATABASE_URL in your .env file")
        return False

    try:
        print("🔌 Connecting to database...")
        engine = create_engine(database_url)

        print("📄 Reading migrations file...")
        with open("db/migrations.sql", "r") as f:
            sql_commands = f.read()

        print("🚀 Applying database schema...")
        with engine.begin() as conn:
            # Split by semicolon and execute each command
            commands = [cmd.strip() for cmd in sql_commands.split(';') if cmd.strip()]

            for i, command in enumerate(commands, 1):
                print(f"   Executing command {i}/{len(commands)}...")
                conn.execute(text(command))

        print("✅ Database initialized successfully!")
        print()
        print("🎯 Next steps:")
        print("   1. Set up Google Sheets API credentials")
        print("   2. Run: python jobs/backfill_weeks.py")
        print("   3. Run: python jobs/ingest_sheet.py")
        print("   4. Launch dashboard: streamlit run app/main.py")

        return True

    except Exception as e:
        print(f"❌ Database setup failed: {e}")
        return False

if __name__ == "__main__":
    setup_database()