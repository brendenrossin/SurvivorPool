#!/usr/bin/env python3
"""
Railway-compatible personal OAuth2 Google Sheets client
Uses environment variables instead of files for Railway deployment
"""

import os
import json
from typing import List, Dict, Any

def get_railway_personal_sheets_client():
    """Get Google Sheets client using OAuth credentials from environment variables"""
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        # Get OAuth credentials from Railway environment variables
        oauth_token = os.getenv('GOOGLE_OAUTH_TOKEN_JSON')

        if not oauth_token:
            print("❌ GOOGLE_OAUTH_TOKEN_JSON environment variable not set")
            return None

        # Parse the token JSON
        token_data = json.loads(oauth_token)

        # Create credentials object
        creds = Credentials.from_authorized_user_info(token_data)

        # Refresh if needed
        if creds.expired and creds.refresh_token:
            print("🔄 Refreshing OAuth token...")
            creds.refresh(Request())

            # Update environment variable with refreshed token (for next time)
            updated_token = creds.to_json()
            print("💾 Token refreshed successfully")

        # Build the service
        service = build('sheets', 'v4', credentials=creds)
        print("✅ Railway personal sheets client ready")
        return service

    except Exception as e:
        print(f"❌ Failed to create Railway sheets client: {e}")
        print(f"🔍 Debug info:")
        print(f"   - GOOGLE_OAUTH_TOKEN_JSON present: {bool(os.getenv('GOOGLE_OAUTH_TOKEN_JSON'))}")
        print(f"   - Token length: {len(os.getenv('GOOGLE_OAUTH_TOKEN_JSON', ''))}")
        import traceback
        traceback.print_exc()
        return None

class RailwayPersonalSheetsClient:
    """Railway-compatible personal OAuth2 sheets client"""

    def __init__(self):
        self.service = get_railway_personal_sheets_client()
        self.spreadsheet_id = os.getenv('GOOGLE_SHEETS_SPREADSHEET_ID')
        self.picks_range = os.getenv('GOOGLE_SHEETS_PICKS_RANGE', 'Picks!A1:Z5000')

    def get_picks_data(self) -> List[Dict[str, Any]]:
        """Get survivor picks data from Google Sheets"""
        if not self.service:
            return []

        try:
            print(f"📊 Reading picks from Railway environment...")

            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=self.picks_range
            ).execute()

            values = result.get('values', [])
            print(f"✅ Retrieved {len(values)} rows from Google Sheets")

            if not values:
                return []

            # Parse data (same logic as before)
            headers = values[0] if values else []
            picks_data = []

            for row_idx, row in enumerate(values[1:], start=2):
                if not row:
                    continue

                while len(row) < len(headers):
                    row.append('')

                pick_record = {
                    'row_number': row_idx,
                    'parsed_data': dict(zip(headers, row[:len(headers)]))
                }
                picks_data.append(pick_record)

            print(f"✅ Parsed {len(picks_data)} survivor picks")
            return picks_data

        except Exception as e:
            print(f"❌ Error reading Railway picks: {e}")
            return []

def main():
    """Test Railway personal sheets client"""
    print("🚂 Testing Railway Personal Sheets Client")
    print("=" * 50)

    client = RailwayPersonalSheetsClient()
    picks_data = client.get_picks_data()

    if picks_data:
        print(f"🎉 Successfully retrieved {len(picks_data)} picks!")
        return True
    else:
        print("❌ No picks retrieved")
        return False

if __name__ == "__main__":
    main()