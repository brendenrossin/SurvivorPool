#!/usr/bin/env python3
"""
One-time backfill for weeks 1-2 of the 2025 NFL season
This should only be run ONCE to populate historical data
"""

import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def main():
    """Run one-time backfill for weeks 1-2"""
    print("🏁 ONE-TIME BACKFILL: Weeks 1-2")
    print("=" * 50)

    load_dotenv()

    try:
        # Import after env is loaded
        from api.database import SessionLocal
        from api.models import Game, JobMeta

        # Check if backfill has already been run
        db = SessionLocal()

        backfill_job = db.query(JobMeta).filter(
            JobMeta.job_name == "one_time_backfill_weeks_1_2"
        ).first()

        if backfill_job:
            print("✅ Backfill already completed!")
            print(f"   Completed at: {backfill_job.last_success_at}")
            return

        # Check if we already have week 1-2 data
        existing_games = db.query(Game).filter(
            Game.season == 2025,
            Game.week.in_([1, 2])
        ).count()

        if existing_games > 0:
            print(f"⚠️  Found {existing_games} existing games for weeks 1-2")
            print("   Proceeding with backfill anyway...")

        # Import the backfill job
        from jobs.backfill_weeks import main as backfill_main

        print("🔄 Running backfill for weeks 1-2...")
        backfill_main()

        # Mark as completed
        job_meta = JobMeta(
            job_name="one_time_backfill_weeks_1_2",
            last_success_at=datetime.now(),
            last_run_at=datetime.now(),
            status="completed",
            message="One-time backfill for weeks 1-2 completed successfully"
        )

        db.add(job_meta)
        db.commit()
        db.close()

        print("✅ One-time backfill completed successfully!")

    except Exception as e:
        print(f"❌ One-time backfill failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)