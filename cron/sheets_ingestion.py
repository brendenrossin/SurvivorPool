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
        # Get the project root directory
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        # Step 1: Proactively refresh OAuth token before ingestion
        print("🔑 Step 1: Refreshing OAuth token...")
        oauth_refresh_path = os.path.join(project_root, "jobs", "refresh_oauth_token.py")
        refresh_result = subprocess.run([
            sys.executable,
            oauth_refresh_path
        ], capture_output=True, text=True, timeout=30, cwd=project_root)

        print(refresh_result.stdout)
        if refresh_result.stderr:
            print("OAuth refresh warnings:", refresh_result.stderr)

        if refresh_result.returncode != 0:
            print("⚠️  OAuth token refresh failed - attempting ingestion anyway")
            print("   Ingestion may fail if token is expired")

        # Step 2: Run sheets ingestion
        print("\n📊 Step 2: Ingesting picks from Google Sheets...")
        script_path = os.path.join(project_root, "jobs", "ingest_personal_sheets.py")

        # Run the sheets ingestion script directly
        result = subprocess.run([
            sys.executable,
            script_path
        ], capture_output=True, text=True, timeout=300, cwd=project_root)

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