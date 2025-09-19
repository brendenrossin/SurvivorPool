#!/usr/bin/env python3
"""
Test personal OAuth2 Google Sheets access with local environment
"""

import os
import sys
from dotenv import load_dotenv

# Load local environment
load_dotenv('.env.local.real')

# Add to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_personal_sheets():
    """Test personal OAuth2 sheets access"""
    print("🔑 Testing Personal OAuth2 Google Sheets Access")
    print("=" * 50)

    try:
        from api.sheets_personal_railway import RailwayPersonalSheetsClient

        # Create client
        client = RailwayPersonalSheetsClient()

        if not client.service:
            print("❌ Failed to create sheets client")
            return False

        # Get picks data
        picks_data = client.get_picks_data()

        if picks_data:
            print(f"✅ Successfully retrieved {len(picks_data)} picks!")
            print(f"📄 Sample data preview:")
            for i, pick in enumerate(picks_data[:3]):
                print(f"   Row {i+1}: {pick.get('parsed_data', {})}")
            return True
        else:
            print("❌ No picks data retrieved")
            return False

    except Exception as e:
        print(f"❌ Error testing personal OAuth: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main test"""
    success = test_personal_sheets()

    if success:
        print("\n🎉 Personal OAuth2 test successful!")
        print("✅ Ready to ingest picks using personal credentials")
    else:
        print("\n❌ Personal OAuth2 test failed")
        print("💡 Check your OAuth token and Google Sheets access")

    return success

if __name__ == "__main__":
    main()