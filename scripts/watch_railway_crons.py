#!/usr/bin/env python3
"""
Watch Railway cron job executions in real-time
"""

import time
import subprocess
import sys

def check_service_status(service_name):
    """Check if a Railway service is running"""
    try:
        result = subprocess.run([
            'railway', 'status', '--service', service_name
        ], capture_output=True, text=True, timeout=10)

        if result.returncode == 0:
            return "✅ Available"
        else:
            return f"❌ Error: {result.stderr.strip()}"
    except:
        return "❓ Unknown"

def get_recent_logs(service_name, lines=10):
    """Get recent logs from Railway service"""
    try:
        result = subprocess.run([
            'railway', 'logs', '--service', service_name, '--lines', str(lines)
        ], capture_output=True, text=True, timeout=15)

        if result.returncode == 0:
            return result.stdout
        else:
            return f"Error getting logs: {result.stderr}"
    except subprocess.TimeoutExpired:
        return "Timeout getting logs"
    except:
        return "Railway CLI not available"

def main():
    """Monitor all cron services"""

    services = ["Odds-Cron", "Scores-Cron", "Sheets-Cron"]

    print("🔍 Railway Cron Job Monitor")
    print("=" * 50)

    # Check Railway CLI availability
    try:
        subprocess.run(['railway', '--version'], capture_output=True, timeout=5)
        print("✅ Railway CLI available")
    except:
        print("❌ Railway CLI not found. Install with: npm install -g @railway/cli")
        print("🔧 Alternative: Use Railway Dashboard → Service → Logs")
        return

    print("\n📊 Service Status Check:")
    for service in services:
        status = check_service_status(service)
        print(f"  {service}: {status}")

    print(f"\n📋 Recent Logs (last 10 lines each):")
    print("=" * 50)

    for service in services:
        print(f"\n🔍 {service}:")
        print("-" * 30)
        logs = get_recent_logs(service, 10)
        print(logs)

    print("\n" + "=" * 50)
    print("💡 To manually trigger:")
    print("  1. Railway Dashboard → Service → Deploy button")
    print("  2. railway run python cron/[script].py --service [Service-Name]")
    print("  3. Watch logs in real-time via Dashboard")

if __name__ == "__main__":
    main()