#!/usr/bin/env python3
"""
Railway Cron Job: Google Sheets Ingestion
Runs daily and on Sundays to ingest picks from Google Sheets
"""

import os
import sys
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jobs.ingest_personal_sheets import SheetsIngestionJob

def main():
    """Main cron job function - exits after completion"""
    print(f"🕐 Starting sheets ingestion cron job at {datetime.now()}")

    try:
        job = SheetsIngestionJob()
        success = job.run()

        if success is not False:  # None or True means success
            print("✅ Sheets ingestion completed successfully")
            sys.exit(0)
        else:
            print("❌ Sheets ingestion failed")
            sys.exit(1)

    except Exception as e:
        print(f"💥 Sheets ingestion cron job crashed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()