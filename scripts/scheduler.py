#!/usr/bin/env python3
"""
Continuous scheduler for Railway deployment
Runs scheduled jobs at specified times
"""

import time
import schedule
import subprocess
import sys
import os
from datetime import datetime

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def run_job(job_script):
    """Run a job script and log the result"""
    try:
        print(f"🕐 Starting {job_script} at {datetime.now()}")
        result = subprocess.run([sys.executable, job_script],
                              capture_output=True, text=True, timeout=300)

        if result.returncode == 0:
            print(f"✅ {job_script} completed successfully")
            if result.stdout:
                print(f"Output: {result.stdout}")
        else:
            print(f"❌ {job_script} failed with return code {result.returncode}")
            if result.stderr:
                print(f"Error: {result.stderr}")

    except subprocess.TimeoutExpired:
        print(f"⏰ {job_script} timed out after 5 minutes")
    except Exception as e:
        print(f"💥 {job_script} crashed: {e}")

def main():
    """Set up scheduled jobs"""
    print("🚀 Starting Railway Scheduler")

    # Daily odds update at 8:00 AM EST
    schedule.every().day.at("13:00").do(run_job, "jobs/update_odds.py")

    # Score updates on Sunday hourly 10am-9pm EST
    for hour in range(15, 24):  # 15:00-23:00 UTC (10am-6pm EST)
        schedule.every().sunday.at(f"{hour:02d}:00").do(run_job, "jobs/update_scores.py")

    for hour in range(0, 3):  # 00:00-02:00 UTC (7pm-9pm EST)
        schedule.every().sunday.at(f"{hour:02d}:00").do(run_job, "jobs/update_scores.py")

    # Score updates Monday/Thursday 9pm EST (02:00 UTC next day)
    schedule.every().tuesday.at("02:00").do(run_job, "jobs/update_scores.py")  # Monday 9pm
    schedule.every().friday.at("02:00").do(run_job, "jobs/update_scores.py")   # Thursday 9pm

    print("📅 Scheduled jobs:")
    for job in schedule.get_jobs():
        print(f"   {job}")

    # Run scheduler loop
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute

if __name__ == "__main__":
    main()