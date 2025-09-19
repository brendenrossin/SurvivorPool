#!/usr/bin/env python3
"""
Helper script to set up Railway environment variables for personal OAuth2
Run this AFTER you've successfully authenticated locally
"""

import os
import json

def main():
    print("🚂 Railway OAuth2 Setup Helper")
    print("=" * 40)

    # Check if we have local OAuth token
    if not os.path.exists('token.json'):
        print("❌ token.json not found")
        print("   You need to run personal OAuth authentication first:")
        print("   python test_personal_sheets.py")
        return

    # Read the token
    with open('token.json', 'r') as f:
        token_data = json.load(f)

    # Convert to environment variable format
    token_json = json.dumps(token_data)

    print("✅ Found local OAuth token")
    print("\n🔑 Railway Environment Variable Setup:")
    print("=" * 50)
    print("In your Railway dashboard, add this environment variable:")
    print()
    print("Variable Name:")
    print("GOOGLE_OAUTH_TOKEN_JSON")
    print()
    print("Variable Value:")
    print(token_json)
    print()
    print("=" * 50)
    print()
    print("📝 Steps:")
    print("1. Go to your Railway project dashboard")
    print("2. Click on your web service")
    print("3. Go to 'Variables' tab")
    print("4. Click 'New Variable'")
    print("5. Name: GOOGLE_OAUTH_TOKEN_JSON")
    print("6. Value: Copy the JSON above")
    print("7. Click 'Add'")
    print()
    print("⚠️  Security Notes:")
    print("- This token gives access to your Google account")
    print("- It's scoped only to read Google Sheets")
    print("- Railway environment variables are encrypted")
    print("- Don't put this in GitHub/version control")

    # Save to a .railway file for easy copying
    with open('.railway_oauth_token.txt', 'w') as f:
        f.write(token_json)

    print(f"\n💾 Token also saved to .railway_oauth_token.txt for easy copying")

if __name__ == "__main__":
    main()