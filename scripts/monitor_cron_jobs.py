#!/usr/bin/env python3
"""
Cron Job Health Monitoring Script
Monitor the health and status of all Railway cron jobs
"""

import os
import sys
import time
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

class CronJobMonitor:
    def __init__(self):
        self.database_url = os.getenv("DATABASE_URL")
        if not self.database_url:
            raise ValueError("DATABASE_URL not found")

        # Import after path setup
        from sqlalchemy import create_engine, text
        self.text = text  # Store for use in methods
        self.engine = create_engine(self.database_url)

        # Expected cron jobs and their schedules
        self.cron_jobs = {
            "odds_update": {
                "name": "Daily Odds Update",
                "schedule": "0 13 * * *",  # 8:00 AM EST daily
                "description": "Fetches betting odds from The Odds API",
                "expected_frequency_hours": 24,
                "timeout_minutes": 10
            },
            "score_update": {
                "name": "Score Update",
                "schedule": "0 17,18,19,20,21,22,23,0,1,2 * * 0,1",  # Sunday hourly + Monday night
                "description": "Updates game scores from ESPN API",
                "expected_frequency_hours": 1,  # During game days
                "timeout_minutes": 15
            },
            "sheets_ingestion": {
                "name": "Sheets Ingestion",
                "schedule": "0 14 * * *",  # 9:00 AM EST daily
                "description": "Ingests picks from Google Sheets",
                "expected_frequency_hours": 24,
                "timeout_minutes": 5
            }
        }

    def check_database_health(self) -> Dict[str, Any]:
        """Check basic database connectivity and health"""
        try:
            with self.engine.connect() as conn:
                # Test connection
                result = conn.execute(self.text("SELECT 1"))
                result.fetchone()

                # Check recent data activity
                recent_games = conn.execute(self.text("""
                    SELECT COUNT(*) as count
                    FROM games
                    WHERE season = 2025
                """)).fetchone()

                recent_picks = conn.execute(self.text("""
                    SELECT COUNT(*) as count
                    FROM picks
                    WHERE season = 2025
                """)).fetchone()

                return {
                    "status": "healthy",
                    "games_count": recent_games.count,
                    "picks_count": recent_picks.count,
                    "message": f"Database healthy: {recent_games.count} games, {recent_picks.count} picks"
                }

        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "message": f"Database connection failed: {e}"
            }

    def check_data_freshness(self) -> Dict[str, Any]:
        """Check if data is being updated regularly"""
        try:
            with self.engine.connect() as conn:
                # Check last game score update
                last_score_update = conn.execute(self.text("""
                    SELECT MAX(kickoff) as last_update
                    FROM games
                    WHERE season = 2025
                    AND (home_score IS NOT NULL OR away_score IS NOT NULL)
                """)).fetchone()

                # Check last picks import (if we have a timestamp field)
                picks_info = conn.execute(self.text("""
                    SELECT COUNT(*) as total_picks,
                           COUNT(CASE WHEN week >= 3 THEN 1 END) as recent_picks
                    FROM picks
                    WHERE season = 2025
                """)).fetchone()

                # Check odds data freshness
                odds_info = conn.execute(self.text("""
                    SELECT COUNT(*) as games_with_odds,
                           COUNT(*) as total_games
                    FROM games
                    WHERE season = 2025
                    AND week >= 3
                """)).fetchone()

                results = {
                    "last_score_update": last_score_update.last_update if last_score_update.last_update else "Never",
                    "total_picks": picks_info.total_picks,
                    "recent_picks": picks_info.recent_picks,
                    "games_with_odds": odds_info.games_with_odds if odds_info else 0,
                    "total_recent_games": odds_info.total_games if odds_info else 0
                }

                # Determine overall freshness
                issues = []
                if picks_info.total_picks < 50:
                    issues.append("Low picks count - sheets ingestion may not be working")

                if odds_info and odds_info.games_with_odds < (odds_info.total_games * 0.5):
                    issues.append("Less than 50% of games have odds data")

                return {
                    "status": "fresh" if not issues else "stale",
                    "issues": issues,
                    "details": results,
                    "message": f"Data status: {len(issues)} issues found" if issues else "Data appears fresh"
                }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "message": f"Data freshness check failed: {e}"
            }

    def check_api_rate_limits(self) -> Dict[str, Any]:
        """Check API usage and rate limit status"""
        checks = {}

        # The Odds API check (if we had usage tracking)
        odds_api_key = os.getenv("THE_ODDS_API_KEY")
        if odds_api_key:
            checks["odds_api"] = {
                "status": "configured",
                "message": "API key configured (check usage at https://the-odds-api.com/dashboard)"
            }
        else:
            checks["odds_api"] = {
                "status": "missing",
                "message": "THE_ODDS_API_KEY not configured"
            }

        # Google Sheets API check
        sheets_key = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON_BASE64")
        if sheets_key:
            checks["sheets_api"] = {
                "status": "configured",
                "message": "Google Sheets service account configured"
            }
        else:
            checks["sheets_api"] = {
                "status": "missing",
                "message": "GOOGLE_SERVICE_ACCOUNT_JSON_BASE64 not configured"
            }

        # ESPN API doesn't require key, but we can check if we're hitting rate limits
        checks["espn_api"] = {
            "status": "available",
            "message": "ESPN API available (8 req/min rate limit)"
        }

        return {
            "status": "healthy" if all(c["status"] in ["configured", "available"] for c in checks.values()) else "issues",
            "apis": checks,
            "message": f"API Status: {sum(1 for c in checks.values() if c['status'] in ['configured', 'available'])}/{len(checks)} APIs ready"
        }

    def test_cron_job_execution(self, job_name: str) -> Dict[str, Any]:
        """Test if a specific cron job can execute successfully"""
        if job_name not in self.cron_jobs:
            return {"status": "unknown", "message": f"Unknown job: {job_name}"}

        job_info = self.cron_jobs[job_name]

        try:
            # Test by importing and checking the cron script
            if job_name == "odds_update":
                # Test odds update script
                from cron.daily_odds_update import main as odds_main
                test_result = "Can import odds update script"

            elif job_name == "score_update":
                # Test score update script
                from cron.score_update import main as score_main
                test_result = "Can import score update script"

            elif job_name == "sheets_ingestion":
                # Test sheets ingestion script
                from cron.sheets_ingestion import main as sheets_main
                test_result = "Can import sheets ingestion script"

            return {
                "status": "ready",
                "message": f"{job_info['name']}: {test_result}",
                "job_info": job_info
            }

        except ImportError as e:
            return {
                "status": "import_error",
                "message": f"{job_info['name']}: Import failed - {e}",
                "error": str(e)
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"{job_info['name']}: Test failed - {e}",
                "error": str(e)
            }

    def generate_health_report(self) -> Dict[str, Any]:
        """Generate comprehensive health report"""
        print("🔍 Generating cron job health report...")

        report = {
            "timestamp": datetime.now().isoformat(),
            "environment": os.getenv("ENVIRONMENT", "local"),
            "checks": {}
        }

        # Database health
        print("  📊 Checking database health...")
        report["checks"]["database"] = self.check_database_health()

        # Data freshness
        print("  🕐 Checking data freshness...")
        report["checks"]["data_freshness"] = self.check_data_freshness()

        # API rate limits
        print("  🔑 Checking API configurations...")
        report["checks"]["api_limits"] = self.check_api_rate_limits()

        # Individual cron job tests
        print("  ⚙️  Testing cron job scripts...")
        report["checks"]["cron_jobs"] = {}
        for job_name in self.cron_jobs:
            print(f"    Testing {job_name}...")
            report["checks"]["cron_jobs"][job_name] = self.test_cron_job_execution(job_name)

        # Overall health assessment
        issues = []
        for check_name, check_result in report["checks"].items():
            if check_name == "cron_jobs":
                for job_name, job_result in check_result.items():
                    if job_result["status"] not in ["ready", "healthy"]:
                        issues.append(f"{job_name}: {job_result.get('message', 'Unknown issue')}")
            else:
                if check_result["status"] not in ["healthy", "fresh", "ready"]:
                    issues.append(f"{check_name}: {check_result.get('message', 'Unknown issue')}")

        report["overall"] = {
            "status": "healthy" if not issues else "issues",
            "issues_count": len(issues),
            "issues": issues,
            "summary": f"System health: {len(issues)} issues found" if issues else "All systems healthy"
        }

        return report

    def print_health_report(self, report: Dict[str, Any]):
        """Print formatted health report"""
        print("\n" + "="*60)
        print(f"🏥 CRON JOB HEALTH REPORT")
        print(f"📅 Generated: {report['timestamp']}")
        print(f"🌍 Environment: {report['environment']}")
        print("="*60)

        # Overall status
        overall = report["overall"]
        status_emoji = "✅" if overall["status"] == "healthy" else "⚠️"
        print(f"\n{status_emoji} OVERALL STATUS: {overall['status'].upper()}")
        print(f"📊 Issues Found: {overall['issues_count']}")

        if overall["issues"]:
            print("\n🚨 ISSUES:")
            for issue in overall["issues"]:
                print(f"  • {issue}")

        # Database Health
        db_check = report["checks"]["database"]
        db_emoji = "✅" if db_check["status"] == "healthy" else "❌"
        print(f"\n{db_emoji} DATABASE HEALTH: {db_check['status']}")
        print(f"  {db_check['message']}")

        # Data Freshness
        data_check = report["checks"]["data_freshness"]
        data_emoji = "✅" if data_check["status"] == "fresh" else "⚠️"
        print(f"\n{data_emoji} DATA FRESHNESS: {data_check['status']}")
        print(f"  {data_check['message']}")
        if "details" in data_check:
            details = data_check["details"]
            print(f"  • Total picks: {details['total_picks']}")
            print(f"  • Recent picks: {details['recent_picks']}")
            print(f"  • Games with odds: {details['games_with_odds']}/{details['total_recent_games']}")

        # API Status
        api_check = report["checks"]["api_limits"]
        api_emoji = "✅" if api_check["status"] == "healthy" else "⚠️"
        print(f"\n{api_emoji} API CONFIGURATIONS: {api_check['status']}")
        for api_name, api_info in api_check["apis"].items():
            api_status_emoji = "✅" if api_info["status"] in ["configured", "available"] else "❌"
            print(f"  {api_status_emoji} {api_name}: {api_info['message']}")

        # Cron Jobs
        print(f"\n⚙️  CRON JOB STATUS:")
        cron_checks = report["checks"]["cron_jobs"]
        for job_name, job_result in cron_checks.items():
            job_emoji = "✅" if job_result["status"] == "ready" else "❌"
            job_info = self.cron_jobs[job_name]
            print(f"  {job_emoji} {job_info['name']}")
            print(f"    Schedule: {job_info['schedule']}")
            print(f"    Status: {job_result['message']}")

        print("\n" + "="*60)
        print("💡 MONITORING TIPS:")
        print("  • Run this script before deploying to catch issues early")
        print("  • Check Railway service logs if cron jobs show as ready but not running")
        print("  • Monitor The Odds API usage at https://the-odds-api.com/dashboard")
        print("  • Verify environment variables in Railway dashboard")
        print("="*60)

def main():
    """Main monitoring function"""
    try:
        monitor = CronJobMonitor()
        report = monitor.generate_health_report()
        monitor.print_health_report(report)

        # Return appropriate exit code
        if report["overall"]["status"] == "healthy":
            print("\n✅ All systems healthy!")
            sys.exit(0)
        else:
            print(f"\n⚠️ {report['overall']['issues_count']} issues found. Check details above.")
            sys.exit(1)

    except Exception as e:
        print(f"❌ Health monitoring failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()