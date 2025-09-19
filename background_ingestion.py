#!/usr/bin/env python3
"""
Background data ingestion that runs after Streamlit starts
This prevents startup timeouts while still populating data
"""

import os
import sys
import time
import threading
from datetime import datetime

# Add to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def run_background_ingestion():
    """Run data ingestion in background thread"""
    print("🔄 Starting background data ingestion...")

    try:
        # Wait a bit for Streamlit to fully start
        time.sleep(10)

        print("📊 Attempting sheets ingestion...")
        from jobs.ingest_personal_sheets import main as ingest_sheets
        sheets_success = ingest_sheets()

        print("🏈 Attempting scores update...")
        from jobs.update_scores import main as update_scores
        scores_success = update_scores()

        if sheets_success and scores_success:
            print("✅ Background ingestion completed successfully!")
        else:
            print("⚠️ Background ingestion completed with warnings")

    except Exception as e:
        print(f"❌ Background ingestion error: {e}")
        import traceback
        traceback.print_exc()

def start_background_ingestion():
    """Start background ingestion in separate thread"""
    if os.getenv('ENVIRONMENT') == 'railway':
        print("🚀 Starting background data ingestion thread...")
        thread = threading.Thread(target=run_background_ingestion, daemon=True)
        thread.start()
        return thread
    else:
        print("💻 Local environment - skipping background ingestion")
        return None

if __name__ == "__main__":
    # Can be run standalone too
    run_background_ingestion()