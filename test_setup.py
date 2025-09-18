#!/usr/bin/env python3
"""
Quick test script to verify everything is working
"""

import os
from dotenv import load_dotenv

def test_environment():
    """Test environment setup"""
    load_dotenv()

    print("🔍 Testing environment setup...")
    print()

    # Check required environment variables
    required_vars = [
        "DATABASE_URL",
        "GOOGLE_SHEETS_SPREADSHEET_ID",
        "GOOGLE_SERVICE_ACCOUNT_JSON_BASE64",
        "NFL_SEASON"
    ]

    missing_vars = []
    for var in required_vars:
        value = os.getenv(var)
        if value:
            if var == "GOOGLE_SERVICE_ACCOUNT_JSON_BASE64":
                print(f"✅ {var}: [SET - {len(value)} chars]")
            else:
                print(f"✅ {var}: {value}")
        else:
            print(f"❌ {var}: NOT SET")
            missing_vars.append(var)

    print()

    if missing_vars:
        print("🚨 Missing environment variables:")
        for var in missing_vars:
            print(f"   - {var}")
        print()
        print("💡 Please add these to your .env file")
        return False

    print("✅ All environment variables are set!")
    return True

def test_database():
    """Test database connection"""
    try:
        from api.database import engine
        print("🔌 Testing database connection...")

        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            print("✅ Database connection successful!")
            return True

    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

def test_google_sheets():
    """Test Google Sheets API"""
    try:
        from api.sheets import GoogleSheetsClient
        print("📊 Testing Google Sheets API...")

        client = GoogleSheetsClient()
        # Just test initialization, don't actually fetch data
        print("✅ Google Sheets client initialized successfully!")
        return True

    except Exception as e:
        print(f"❌ Google Sheets setup failed: {e}")
        return False

def test_nfl_api():
    """Test NFL data provider"""
    try:
        from api.score_providers import get_score_provider
        print("🏈 Testing NFL API...")

        provider = get_score_provider("espn")
        season = int(os.getenv("NFL_SEASON", 2025))
        current_week = provider.get_current_week(season)
        print(f"✅ NFL API working! Current week: {current_week}")
        return True

    except Exception as e:
        print(f"❌ NFL API test failed: {e}")
        return False

if __name__ == "__main__":
    from sqlalchemy import text

    print("🚀 SurvivorPool Dashboard Setup Test")
    print("=" * 50)

    tests = [
        ("Environment Variables", test_environment),
        ("Database Connection", test_database),
        ("Google Sheets API", test_google_sheets),
        ("NFL Data API", test_nfl_api),
    ]

    all_passed = True
    for name, test_func in tests:
        print(f"\n🧪 {name}")
        print("-" * 30)
        if not test_func():
            all_passed = False

    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 ALL TESTS PASSED! You're ready to rock!")
        print()
        print("🚀 Next steps:")
        print("   1. python jobs/backfill_weeks.py")
        print("   2. python jobs/ingest_sheet.py")
        print("   3. streamlit run app/main.py")
    else:
        print("⚠️  Some tests failed. Fix the issues above and try again.")