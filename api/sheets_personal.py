#!/usr/bin/env python3
"""
Google Sheets client using personal OAuth2 credentials
This bypasses service account permission issues by using your personal Google account
"""

import os
import sys
from typing import List, Dict, Any, Optional
from datetime import datetime

def get_personal_sheets_client():
    """Get Google Sheets client using personal OAuth2 credentials"""
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build

        # Scopes needed for Google Sheets
        SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']

        creds = None

        # Check if we have saved credentials
        if os.path.exists('token.json'):
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)

        # If there are no (valid) credentials available, authenticate
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                print("🔄 Refreshing OAuth credentials...")
                creds.refresh(Request())
            else:
                if not os.path.exists('credentials.json'):
                    raise Exception("credentials.json not found - OAuth2 setup required")

                print("🔐 Authenticating with personal Google account...")
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)

            # Save the credentials for next time
            with open('token.json', 'w') as token:
                token.write(creds.to_json())

        # Build and return the sheets service
        service = build('sheets', 'v4', credentials=creds)
        print("✅ Personal Google Sheets client ready")
        return service

    except Exception as e:
        print(f"❌ Failed to create personal sheets client: {e}")
        return None

class PersonalSheetsClient:
    """Google Sheets client using personal OAuth2"""

    def __init__(self):
        self.service = get_personal_sheets_client()
        self.spreadsheet_id = os.getenv('GOOGLE_SHEETS_SPREADSHEET_ID')
        self.picks_range = os.getenv('GOOGLE_SHEETS_PICKS_RANGE', 'Picks!A1:Z5000')

    def test_access(self) -> bool:
        """Test if we can access the spreadsheet"""
        if not self.service:
            return False

        try:
            # Try to get sheet metadata
            result = self.service.spreadsheets().get(
                spreadsheetId=self.spreadsheet_id
            ).execute()

            title = result.get('properties', {}).get('title', 'Unknown')
            print(f"✅ Can access sheet: {title}")
            return True

        except Exception as e:
            print(f"❌ Cannot access sheet: {e}")
            return False

    def get_picks_data(self) -> List[Dict[str, Any]]:
        """Get survivor picks data from the Google Sheet"""
        if not self.service:
            print("❌ No sheets service available")
            return []

        try:
            print(f"📊 Reading picks data from: {self.picks_range}")

            # Get the raw data
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=self.picks_range
            ).execute()

            values = result.get('values', [])
            print(f"📋 Retrieved {len(values)} rows from Google Sheets")

            if not values:
                print("⚠️ No data found in sheet")
                return []

            # Parse the data (assuming first row is headers)
            headers = values[0] if values else []
            picks_data = []

            for row_idx, row in enumerate(values[1:], start=2):
                if not row:  # Skip empty rows
                    continue

                # Pad row with empty strings if it's shorter than headers
                while len(row) < len(headers):
                    row.append('')

                # Create pick record
                pick_record = {
                    'row_number': row_idx,
                    'raw_data': row[:len(headers)],
                    'parsed_data': dict(zip(headers, row[:len(headers)]))
                }

                picks_data.append(pick_record)

            print(f"✅ Parsed {len(picks_data)} pick records")
            return picks_data

        except Exception as e:
            print(f"❌ Error reading picks data: {e}")
            import traceback
            traceback.print_exc()
            return []

    def save_debug_data(self, picks_data: List[Dict[str, Any]]) -> None:
        """Save picks data for debugging"""
        try:
            import json
            os.makedirs("debug_output", exist_ok=True)

            with open('debug_output/personal_sheets_picks.json', 'w') as f:
                json.dump(picks_data, f, indent=2, default=str)

            print(f"💾 Debug data saved to debug_output/personal_sheets_picks.json")

        except Exception as e:
            print(f"⚠️ Could not save debug data: {e}")

def main():
    """Test the personal sheets client"""
    print("🔑 Testing Personal Google Sheets Client")
    print("=" * 50)

    # Load environment
    from dotenv import load_dotenv
    load_dotenv()

    # Create client and test
    client = PersonalSheetsClient()

    if not client.test_access():
        print("❌ Cannot access Google Sheets")
        return False

    # Get picks data
    picks_data = client.get_picks_data()

    if picks_data:
        print(f"\n📊 Sample of picks data:")
        for i, pick in enumerate(picks_data[:3]):
            print(f"   Row {pick['row_number']}: {pick['parsed_data']}")

        # Save for inspection
        client.save_debug_data(picks_data)

        print(f"\n🎉 Successfully retrieved {len(picks_data)} picks from Google Sheets!")
        return True
    else:
        print("❌ No picks data retrieved")
        return False

if __name__ == "__main__":
    main()