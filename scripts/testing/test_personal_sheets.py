#!/usr/bin/env python3
"""
Test Google Sheets access using personal OAuth2 credentials instead of service account
This bypasses the service account permission issue
"""

import os
import sys
from dotenv import load_dotenv

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def setup_personal_oauth():
    """
    Set up OAuth2 flow for personal Google account access
    This will open a browser for one-time authentication
    """
    print("🔐 Setting up Personal Google OAuth2 Access")
    print("=" * 50)

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
            print("📄 Found existing credentials...")
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)

        # If there are no (valid) credentials available, let the user log in
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                print("🔄 Refreshing expired credentials...")
                creds.refresh(Request())
            else:
                print("🌐 Need to authenticate - this will open your browser...")
                print("❗ You'll need to create OAuth2 credentials first!")
                print("\nTo create OAuth2 credentials:")
                print("1. Go to: https://console.cloud.google.com/apis/credentials")
                print("2. Click 'Create Credentials' > 'OAuth client ID'")
                print("3. Application type: 'Desktop application'")
                print("4. Download the JSON file as 'credentials.json'")
                print("5. Put it in this directory and run this script again")

                if not os.path.exists('credentials.json'):
                    print("\n❌ credentials.json not found - please create it first")
                    return None

                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)

            # Save the credentials for the next run
            with open('token.json', 'w') as token:
                token.write(creds.to_json())
                print("💾 Saved credentials for future use")

        print("✅ Personal OAuth2 credentials ready!")
        return creds

    except ImportError as e:
        print(f"❌ Missing required library: {e}")
        print("Install with: pip install google-auth-oauthlib")
        return None
    except Exception as e:
        print(f"❌ OAuth2 setup failed: {e}")
        return None

def test_personal_sheets_access():
    """Test accessing the Google Sheet with personal credentials"""
    print("\n📊 Testing Personal Google Sheets Access")
    print("=" * 50)

    # Set up personal OAuth
    creds = setup_personal_oauth()
    if not creds:
        return False

    try:
        from googleapiclient.discovery import build

        # Build the service
        service = build('sheets', 'v4', credentials=creds)

        # Test sheet access
        load_dotenv()
        spreadsheet_id = os.getenv('GOOGLE_SHEETS_SPREADSHEET_ID')
        picks_range = os.getenv('GOOGLE_SHEETS_PICKS_RANGE', 'Picks!A1:Z1000')

        print(f"📋 Testing access to sheet: {spreadsheet_id}")
        print(f"📋 Reading range: {picks_range}")

        # Get sheet metadata
        sheet_metadata = service.spreadsheets().get(
            spreadsheetId=spreadsheet_id
        ).execute()

        title = sheet_metadata.get('properties', {}).get('title', 'Unknown')
        sheets = sheet_metadata.get('sheets', [])
        sheet_names = [s['properties']['title'] for s in sheets]

        print(f"✅ Sheet access successful!")
        print(f"   Title: {title}")
        print(f"   Available tabs: {sheet_names}")

        # Read actual data
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=picks_range
        ).execute()

        values = result.get('values', [])
        print(f"✅ Data read successful!")
        print(f"   Rows returned: {len(values)}")

        if values:
            print(f"   Header row: {values[0] if len(values) > 0 else 'None'}")
            if len(values) > 1:
                print(f"   Sample data row: {values[1]}")

            # Save for inspection
            import json
            os.makedirs("debug_output", exist_ok=True)
            with open('debug_output/personal_sheets_data.json', 'w') as f:
                json.dump(values, f, indent=2)
            print(f"   💾 Data saved to debug_output/personal_sheets_data.json")

        return True

    except Exception as e:
        print(f"❌ Sheets access failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("🔑 Personal Google Sheets Access Test")
    print("This uses your personal Google account instead of service account")
    print("=" * 60)

    success = test_personal_sheets_access()

    if success:
        print("\n🎉 Personal Google Sheets access working!")
        print("💡 You can now use this method to bypass service account issues")
    else:
        print("\n❌ Personal access failed")
        print("💡 You may need to set up OAuth2 credentials first")

if __name__ == "__main__":
    main()