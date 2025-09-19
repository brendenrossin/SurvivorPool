#!/usr/bin/env python3
"""
Simple Google Sheets test with longer timeout
"""

import os
import sys
import base64
import json
import socket
from dotenv import load_dotenv

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_simple_access():
    print("🔐 Simple Google Sheets Access Test")
    print("=" * 40)

    load_dotenv()

    try:
        # Test network connectivity first
        print("🌐 Testing network connectivity...")
        try:
            socket.create_connection(("sheets.googleapis.com", 443), timeout=10)
            print("✅ Network connection to Google Sheets API working")
        except Exception as e:
            print(f"❌ Network issue: {e}")
            return False

        # Import with longer timeout
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        import httplib2

        # Create credentials
        creds_b64 = os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON_BASE64')
        creds_json = base64.b64decode(creds_b64).decode('utf-8')
        creds_dict = json.loads(creds_json)

        credentials = service_account.Credentials.from_service_account_info(
            creds_dict,
            scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
        )

        # Build service with longer timeout
        http = httplib2.Http(timeout=60)
        service = build('sheets', 'v4', credentials=credentials, http=http)

        print("🔍 Testing sheet access with 60-second timeout...")
        spreadsheet_id = os.getenv('GOOGLE_SHEETS_SPREADSHEET_ID')

        # Try to access the sheet
        try:
            sheet_metadata = service.spreadsheets().get(
                spreadsheetId=spreadsheet_id,
                fields='properties.title,sheets.properties.title'
            ).execute()

            print("🎉 SUCCESS! Sheet access working!")
            title = sheet_metadata.get('properties', {}).get('title', 'Unknown')
            print(f"   Sheet title: {title}")

            sheets = sheet_metadata.get('sheets', [])
            sheet_names = [s['properties']['title'] for s in sheets]
            print(f"   Available tabs: {sheet_names}")

            return True

        except Exception as e:
            error_msg = str(e)
            print(f"❌ Sheet access failed: {error_msg}")

            if "403" in error_msg:
                print("   → This is a permissions error")
                print("   → The service account needs access to the sheet")
            elif "404" in error_msg:
                print("   → The sheet ID might be wrong or sheet doesn't exist")
            elif "timeout" in error_msg.lower():
                print("   → Network timeout - try again in a few minutes")

            return False

    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    success = test_simple_access()

    if not success:
        print("\n🔧 Troubleshooting Tips:")
        print("1. Check Google Cloud Console: https://console.cloud.google.com/iam-admin/serviceaccounts?project=nflsurvivorpool")
        print("2. Verify Google Sheets API is enabled: https://console.cloud.google.com/apis/dashboard?project=nflsurvivorpool")
        print("3. Confirm sheet sharing with: survivorpool-sheets@nflsurvivorpool.iam.gserviceaccount.com")
        print("4. Sometimes permissions take 5-10 minutes to propagate")