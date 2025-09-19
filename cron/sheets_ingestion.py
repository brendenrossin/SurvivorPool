#!/usr/bin/env python3
"""
Railway Cron Job: Google Sheets Ingestion
Runs daily and on Sundays to ingest picks from Google Sheets
"""

import os
import sys
import subprocess
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    """Main cron job function - exits after completion"""
    print(f"🕐 Starting sheets ingestion cron job at {datetime.now()}")

    try:
        # Run the sheets ingestion script directly
        result = subprocess.run([
            sys.executable,
            "jobs/ingest_personal_sheets.py"
        ], capture_output=True, text=True, timeout=300)

        print("📊 Sheets ingestion output:")
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print("Errors:", result.stderr)

        if result.returncode == 0:
            print("✅ Sheets ingestion completed successfully")
            sys.exit(0)
        else:
            print(f"❌ Sheets ingestion failed with return code {result.returncode}")
            sys.exit(1)

    except subprocess.TimeoutExpired:
        print("⏰ Sheets ingestion timed out after 5 minutes")
        sys.exit(1)
    except Exception as e:
        print(f"💥 Sheets ingestion cron job crashed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()