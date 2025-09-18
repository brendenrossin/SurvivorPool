#!/usr/bin/env python3
"""
Local testing script - full end-to-end test with local SQLite database
"""

import os
import sys
import shutil
from dotenv import load_dotenv

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def setup_local_env():
    """Set up local environment"""
    print("🛠️  Setting up local test environment...")

    # Create debug output directory
    os.makedirs("debug_output", exist_ok=True)

    # Check for local env file
    if not os.path.exists(".env.local.real"):
        print("   ⚠️  No .env.local.real found")
        print("   📝 Copy .env.local to .env.local.real and add your Google credentials")
        print("   💡 You can test NFL API without Google Sheets")
        return False

    # Load local environment
    load_dotenv(".env.local.real")
    print("   ✅ Local environment loaded")
    return True

def test_local_database():
    """Test with local SQLite database"""
    print("\n💾 Testing local SQLite database...")

    try:
        # Import after env is loaded
        from api.database import engine, SessionLocal
        from api.models import Base

        # Create all tables
        print("   Creating database tables...")
        Base.metadata.create_all(bind=engine)

        # Test connection
        from sqlalchemy import text
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()

        print("   ✅ Local database created and tested")
        return True

    except Exception as e:
        print(f"   ❌ Database setup failed: {e}")
        return False

def run_local_tests():
    """Run the full test suite locally"""
    print("\n🧪 Running local data source tests...")

    try:
        # Import and run the debug script
        import debug_data_sources
        debug_data_sources.main()
        return True

    except Exception as e:
        print(f"❌ Local tests failed: {e}")
        return False

def run_local_jobs():
    """Test the actual jobs locally"""
    print("\n⚙️  Testing jobs locally...")

    try:
        print("   Testing sheet ingestion...")
        from jobs.ingest_sheet import SheetIngestor
        ingestor = SheetIngestor()
        ingestor.run()

        print("   Testing score updates...")
        from jobs.update_scores import ScoreUpdater
        updater = ScoreUpdater()
        updater.run()

        print("   ✅ Jobs completed successfully")
        return True

    except Exception as e:
        print(f"   ⚠️  Jobs completed with issues: {e}")
        print("   (This is expected if Google Sheets access isn't configured)")
        return False

def view_results():
    """Export database for inspection"""
    print("\n🔍 Exporting database for inspection...")

    try:
        import view_database
        view_database.main()
        return True

    except Exception as e:
        print(f"❌ Database export failed: {e}")
        return False

def main():
    """Run full local test suite"""
    print("🚀 SurvivorPool Local Test Suite")
    print("=" * 50)

    # Setup
    if not setup_local_env():
        print("\n💡 To run full tests:")
        print("   1. Copy .env.local to .env.local.real")
        print("   2. Add your Google credentials to .env.local.real")
        print("   3. Run this script again")
        print("\n🧪 Running partial tests (NFL API only)...")

        # Load default env for partial testing
        load_dotenv()

    # Test database
    if not test_local_database():
        print("❌ Cannot continue without database")
        return

    # Run tests
    run_local_tests()

    # Run jobs (may fail without Google Sheets)
    run_local_jobs()

    # Export results
    view_results()

    print("\n" + "=" * 50)
    print("🎯 LOCAL TEST COMPLETE!")
    print("\n📁 Check these files in VS Code:")
    print("   - debug_output/ (all test outputs)")
    print("   - debug_output/local_survivor.db (SQLite database)")
    print("\n💡 You can open the .db file with SQLite extensions in VS Code!")

if __name__ == "__main__":
    main()