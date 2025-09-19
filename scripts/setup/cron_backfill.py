#!/usr/bin/env python3
"""
Railway Cron Job: Backfill historical weeks data
Runs once daily to ensure all past weeks are properly processed
"""

import os
import sys
import traceback
from datetime import datetime
from dotenv import load_dotenv

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def main():
    """Run backfill as a cron job"""
    print(f"🕐 Cron Job Started: Weekly Backfill at {datetime.now()} UTC")

    try:
        load_dotenv()

        # Import and run the backfill job
        from jobs.backfill_weeks import main as backfill_main

        backfill_main()
        print("✅ Weekly backfill completed successfully")

    except Exception as e:
        print(f"❌ Weekly backfill failed: {e}")
        traceback.print_exc()
        # Exit with error code for Railway monitoring
        sys.exit(1)

    print("🏁 Cron Job Completed: Weekly Backfill")
    # Successful exit
    sys.exit(0)

if __name__ == "__main__":
    main()