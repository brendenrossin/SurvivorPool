#!/usr/bin/env python3
"""
Service Account Google Sheets Ingestion

This is a THIN WRAPPER that handles service account authentication,
then uses the gold standard logic from sheets_ingestion_shared.py
"""

import os
import sys

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.sheets import GoogleSheetsClient
from dotenv import load_dotenv
from jobs.sheets_ingestion_shared import (
    parse_picks_data,
    ingest_players_and_picks,
    populate_historical_eliminations
)


def main(argv=None):
    """Main ingestion process using service account"""
    import argparse

    parser = argparse.ArgumentParser(description="Ingest picks from Google Sheets")
    parser.add_argument(
        "--force", action="store_true",
        help="Re-ingest even if the sheet is unchanged since the last run. "
             "The hourly schedule relies on the fingerprint skip; this is the "
             "escape hatch for forcing a refresh by hand.")
    args = parser.parse_args(argv)

    print("📊 Service Account Google Sheets Ingestion")
    print("=" * 50)

    # Load environment
    load_dotenv()

    # AUTHENTICATION: Service account
    client = GoogleSheetsClient()
    raw_data = client.get_picks_data()

    if not raw_data:
        print("⚠️ No data retrieved from Google Sheets (check service account)")
        return True  # Don't fail deployment, just skip ingestion

    # Use GOLD STANDARD shared logic for everything else
    players_data = parse_picks_data(raw_data)

    if not players_data:
        print("⚠️ No valid picks data parsed")
        return True  # Don't fail deployment

    # Ingest into database
    success = ingest_players_and_picks(players_data, source_label="google_sheets",
                                       force=args.force)

    if success:
        print("\n🎉 Service account ingestion successful!")
        print("🚀 Your dashboard should now show real survivor picks!")

        # Populate historical eliminations
        populate_historical_eliminations()
    else:
        print("\n❌ Service account ingestion failed")

    return success


if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)
