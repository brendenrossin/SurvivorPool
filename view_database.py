#!/usr/bin/env python3
"""
Simple database viewer - exports all tables to JSON for VS Code inspection
"""

import os
import json
import sys
from datetime import datetime
from dotenv import load_dotenv

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

load_dotenv()

def export_table_to_json(db, model_class, filename):
    """Export a table to JSON format"""
    try:
        records = db.query(model_class).all()

        # Convert to JSON-serializable format
        data = []
        for record in records:
            record_dict = {}
            for column in model_class.__table__.columns:
                value = getattr(record, column.name)
                # Handle datetime objects
                if hasattr(value, 'isoformat'):
                    value = value.isoformat()
                record_dict[column.name] = value
            data.append(record_dict)

        # Save to file
        with open(f"debug_output/{filename}", "w") as f:
            json.dump(data, f, indent=2, default=str)

        print(f"   ✅ {filename}: {len(data)} records")
        return len(data)

    except Exception as e:
        print(f"   ❌ {filename}: Error - {e}")
        return 0

def main():
    """Export all database tables"""
    print("💾 Database Viewer - Exporting all tables to JSON")
    print("=" * 50)

    try:
        from api.database import SessionLocal
        from api.models import Player, Pick, Game, PickResult, JobMeta

        # Create debug output directory
        os.makedirs("debug_output", exist_ok=True)

        db = SessionLocal()

        # Export all tables
        print("📊 Exporting tables...")

        total_records = 0
        total_records += export_table_to_json(db, Player, "table_players.json")
        total_records += export_table_to_json(db, Pick, "table_picks.json")
        total_records += export_table_to_json(db, Game, "table_games.json")
        total_records += export_table_to_json(db, PickResult, "table_pick_results.json")
        total_records += export_table_to_json(db, JobMeta, "table_job_meta.json")

        # Create a summary
        summary = {
            "export_time": datetime.now().isoformat(),
            "total_records": total_records,
            "database_url": os.getenv("DATABASE_URL", "Not set").split("@")[1] if "@" in os.getenv("DATABASE_URL", "") else "Local",
            "files_created": [
                "table_players.json",
                "table_picks.json",
                "table_games.json",
                "table_pick_results.json",
                "table_job_meta.json"
            ]
        }

        with open("debug_output/database_export_summary.json", "w") as f:
            json.dump(summary, f, indent=2)

        db.close()

        print(f"\n✅ Export complete!")
        print(f"   Total records: {total_records}")
        print(f"   Files saved to: debug_output/")
        print(f"\n🔍 Open these files in VS Code to inspect your database:")
        for filename in summary["files_created"]:
            print(f"   - debug_output/{filename}")

    except Exception as e:
        print(f"❌ Database export failed: {e}")

        # Save error
        with open("debug_output/database_export_error.txt", "w") as f:
            f.write(f"Error: {e}\n")
            f.write(f"Time: {datetime.now()}\n")

if __name__ == "__main__":
    main()