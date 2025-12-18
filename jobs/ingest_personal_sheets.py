#!/usr/bin/env python3
"""
OAuth Personal Google Sheets Ingestion

This is a THIN WRAPPER that handles OAuth authentication,
then uses the gold standard logic from sheets_ingestion_shared.py
"""

import os
import sys

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.sheets_personal_railway import RailwayPersonalSheetsClient
from dotenv import load_dotenv
from jobs.sheets_ingestion_shared import (
    parse_picks_data,
    ingest_players_and_picks,
    populate_historical_eliminations
)


def convert_oauth_format_to_raw(picks_data):
    """Convert OAuth client format to raw rows format

    OAuth format: [{'row_number': 2, 'parsed_data': {'Name': 'Aditya', ...}}, ...]
    Raw format: [['Name', 'Week 1', ...], ['Aditya', 'ARI', ...], ...]

    This adapter allows OAuth data to use the same shared parsing logic.
    """
    if not picks_data or len(picks_data) == 0:
        return []

    # Get headers from first record
    first_record = picks_data[0]
    headers = list(first_record['parsed_data'].keys())

    # Build raw format
    raw_data = [headers]  # First row is header

    for record in picks_data:
        row = []
        for header in headers:
            row.append(record['parsed_data'].get(header, ''))
        raw_data.append(row)

    return raw_data


def main():
    """Main ingestion process using OAuth"""
    print("📊 Personal OAuth2 Google Sheets Ingestion")
    print("=" * 50)

    # Load environment
    load_dotenv()

    # AUTHENTICATION: OAuth
    client = RailwayPersonalSheetsClient()
    oauth_data = client.get_picks_data()

    if not oauth_data:
        print("⚠️ No data retrieved from Google Sheets (check OAuth credentials)")
        return True  # Don't fail deployment, just skip ingestion

    # Convert OAuth format to raw format
    raw_data = convert_oauth_format_to_raw(oauth_data)

    # Use GOLD STANDARD shared logic for everything else
    players_data = parse_picks_data(raw_data)

    if not players_data:
        print("⚠️ No valid picks data parsed")
        return True  # Don't fail deployment

    # Ingest into database
    success = ingest_players_and_picks(players_data, source_label="google_sheets_personal")

    if success:
        print("\n🎉 Personal OAuth2 ingestion successful!")
        print("🚀 Your dashboard should now show real survivor picks!")

        # Populate historical eliminations
        populate_historical_eliminations()
    else:
        print("\n❌ Personal OAuth2 ingestion failed")

    return success


if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)
