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
        return True

    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        return False

if __name__ == "__main__":
    init_railway_db()