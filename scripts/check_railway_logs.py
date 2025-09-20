#!/usr/bin/env python3
"""
Check Railway cron job logs using Railway CLI
"""

import os
import subprocess
import sys

def run_railway_command(cmd):
    """Run railway CLI command and return output"""
    try:
        result = subprocess.run(
            ['railway'] + cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        return result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        return "", "Command timed out", 1
    except FileNotFoundError:
        return "", "Railway CLI not installed", 1

def check_service_logs(service_name, lines=20):
    """Check logs for a specific service"""
    print(f"\n📊 {service_name} - Recent Logs:")
    print("-" * 50)

    stdout, stderr, code = run_railway_command([
        'logs', '--service', service_name, '--lines', str(lines)
    ])

    if code == 0:
        if stdout.strip():
            print(stdout)
        else:
            print("No logs found")
    else:
        print(f"❌ Error getting logs: {stderr}")

def main():
    """Check all cron service logs"""

    # Check if Railway CLI is available
    stdout, stderr, code = run_railway_command(['--version'])
    if code != 0:
        print("❌ Railway CLI not installed or not logged in")
        print("Install: npm install -g @railway/cli")
        print("Login: railway login")
        return

    print("🔍 Railway Cron Job Log Check")
    print("=" * 60)

    # List of cron services to check
    services = [
        "Odds-Cron",
        "Scores-Cron",
        "Sheets-Cron"
    ]

    for service in services:
        check_service_logs(service)

    print("\n" + "=" * 60)
    print("💡 What to look for:")
    print("  ✅ Scripts that start, run, and exit cleanly")
    print("  ❌ Scripts that keep running or show Streamlit startup")
    print("  ✅ Exit codes: 0 = success, 1 = failure")
    print("  ❌ If you see Streamlit logs, start command is wrong")

if __name__ == "__main__":
    main()