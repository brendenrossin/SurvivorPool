#!/usr/bin/env python3
"""
OAuth Health Monitoring
Checks if OAuth token refresh is working and alerts if issues detected
"""

import os
import sys
from datetime import datetime, timedelta, timezone

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.database import SessionLocal
from api.models import JobMeta

def check_oauth_health():
    """Check OAuth health by monitoring job failures"""
    db = SessionLocal()
    try:
        print(f"🏥 OAuth Health Check at {datetime.now(timezone.utc)}")

        # Check sheets ingestion job status
        sheets_job = db.query(JobMeta).filter(
            JobMeta.job_name == "ingest_sheet"
        ).first()

        if not sheets_job:
            print("⚠️  No sheets ingestion job found in database")
            return False

        print(f"\n📊 Sheets Ingestion Job Status:")
        print(f"   Status: {sheets_job.status}")
        print(f"   Last run: {sheets_job.last_run_at}")
        print(f"   Last success: {sheets_job.last_success_at}")
        print(f"   Message: {sheets_job.message}")

        # Check if job has failed recently (last 24 hours)
        now = datetime.now(timezone.utc)
        last_run = sheets_job.last_run_at

        # Ensure timezone awareness
        if last_run and last_run.tzinfo is None:
            last_run = last_run.replace(tzinfo=timezone.utc)

        # Check for OAuth-related failures
        oauth_failure_keywords = [
            "invalid_grant",
            "Token has been expired",
            "OAuth",
            "credentials",
            "authentication"
        ]

        is_oauth_failure = any(
            keyword.lower() in (sheets_job.message or "").lower()
            for keyword in oauth_failure_keywords
        )

        # Alert conditions
        alerts = []

        if sheets_job.status == "error" and is_oauth_failure:
            alerts.append("🚨 CRITICAL: OAuth authentication failure detected!")
            alerts.append(f"   Error: {sheets_job.message}")

        if last_run and (now - last_run) > timedelta(hours=48):
            alerts.append("⚠️  WARNING: Sheets ingestion hasn't run in 48+ hours")

        if sheets_job.last_success_at:
            last_success = sheets_job.last_success_at
            if last_success.tzinfo is None:
                last_success = last_success.replace(tzinfo=timezone.utc)

            if (now - last_success) > timedelta(hours=72):
                alerts.append("🚨 CRITICAL: No successful ingestion in 72+ hours")

        # Print alerts
        if alerts:
            print("\n" + "=" * 60)
            print("⚠️  ALERTS DETECTED:")
            print("=" * 60)
            for alert in alerts:
                print(alert)
            print("=" * 60)
            print("\n💡 Recommended Actions:")
            print("   1. Check Railway logs for sheets-ingestion cron")
            print("   2. Verify GOOGLE_OAUTH_TOKEN_JSON is valid")
            print("   3. If token revoked, regenerate with:")
            print("      python scripts/testing/test_personal_sheets.py")
            print("   4. Update Railway environment variable")
            return False
        else:
            print("\n✅ OAuth health check passed - no issues detected")
            return True

    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False
    finally:
        db.close()

if __name__ == "__main__":
    healthy = check_oauth_health()
    sys.exit(0 if healthy else 1)
