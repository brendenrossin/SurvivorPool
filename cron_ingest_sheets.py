#!/usr/bin/env python3
"""
Railway Cron Job: Ingest Google Sheets picks data
Runs every hour to keep picks data fresh
"""

import os
import sys
import traceback
from datetime import datetime
from dotenv import load_dotenv

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def main():
    """Run sheets ingestion as a cron job"""
    print(f"🕐 Cron Job Started: Sheets Ingestion at {datetime.now()} UTC")

    try:
        load_dotenv()

        # Import and run the sheets ingestor
        from jobs.ingest_sheet import SheetIngestor

        ingestor = SheetIngestor()
        result = ingestor.run()

        if result:
            print("✅ Sheets ingestion completed successfully")
        else:
            print("⚠️  Sheets ingestion completed with warnings")

    except Exception as e:
        print(f"❌ Sheets ingestion failed: {e}")
        traceback.print_exc()
        # Exit with error code for Railway monitoring
        sys.exit(1)

    print("🏁 Cron Job Completed: Sheets Ingestion")
    # Successful exit
    sys.exit(0)

if __name__ == "__main__":
    main()