#!/usr/bin/env python3
"""
Test Google Sheets access with more detailed error reporting
"""

import os
import sys
import base64
import json
from dotenv import load_dotenv

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_sheets_access():
    print("🔐 Testing Google Sheets Access After Permission Sharing")
    print("=" * 60)

    # Load environment
    load_dotenv()

    try:
        # Test credentials decoding
        print("🔑 Step 1: Testing credentials...")
        creds_b64 = os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON_BASE64')
        if not creds_b64:
            print("❌ No GOOGLE_SERVICE_ACCOUNT_JSON_BASE64 found")
            return False

        creds_json = base64.b64decode(creds_b64).decode('utf-8')
        creds_dict = json.loads(creds_json)
        print(f"✅ Credentials decoded successfully")
        print(f"   Service Account: {creds_dict.get('client_email')}")

        # Test Google API imports
        print("\n📦 Step 2: Testing Google API imports...")
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        print("✅ Google API libraries imported successfully")

        # Create credentials
        print("\n🔐 Step 3: Creating credentials...")
        credentials = service_account.Credentials.from_service_account_info(
            creds_dict,
            scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
        )
        print("✅ Service account credentials created")

        # Build service
        print("\n🌐 Step 4: Building Google Sheets service...")
        service = build('sheets', 'v4', credentials=credentials)
        print("✅ Google Sheets service built successfully")

        # Test sheet access
        print("\n📊 Step 5: Testing sheet access...")
        spreadsheet_id = os.getenv('GOOGLE_SHEETS_SPREADSHEET_ID')
        print(f"   Spreadsheet ID: {spreadsheet_id}")

        # Try to get sheet metadata first
        try:
            sheet_metadata = service.spreadsheets().get(
                spreadsheetId=spreadsheet_id
            ).execute()

            print("✅ Sheet metadata retrieved successfully!")
            print(f"   Title: {sheet_metadata.get('properties', {}).get('title', 'Unknown')}")

            # List available sheets
            sheets = sheet_metadata.get('sheets', [])
            print(f"   Available sheets: {[s['properties']['title'] for s in sheets]}")

        except Exception as e:
            print(f"❌ Cannot access sheet metadata: {e}")
            print("   This usually means the service account doesn't have access")
            return False

        # Test reading actual data
        print("\n📋 Step 6: Testing data reading...")
        try:
            picks_range = os.getenv('GOOGLE_SHEETS_PICKS_RANGE', 'Picks!A1:Z1000')
            result = service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=picks_range
            ).execute()

            values = result.get('values', [])
            print(f"✅ Data retrieved successfully!")
            print(f"   Rows returned: {len(values)}")

            if values:
                print(f"   Header row: {values[0] if len(values) > 0 else 'None'}")
                print(f"   Sample data: {values[1] if len(values) > 1 else 'No data rows'}")

            return True

        except Exception as e:
            print(f"❌ Cannot read data: {e}")
            return False

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_sheets_access()

    if success:
        print("\n🎉 Google Sheets Access: SUCCESS!")
        print("✅ The service account now has proper access to your sheet")
        print("🚀 Ready to run full data population!")
    else:
        print("\n❌ Google Sheets Access: FAILED!")
        print("📧 Make sure you shared the sheet with: survivorpool-sheets@nflsurvivorpool.iam.gserviceaccount.com")
        print("🔧 Check the Google Cloud Console links above for troubleshooting")