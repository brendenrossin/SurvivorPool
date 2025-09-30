#!/usr/bin/env python3
"""
Refresh expired Google OAuth token
"""

import os
import json
import base64
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

def refresh_oauth_token():
    """Refresh the OAuth token"""

    # Load current token
    token_json = os.getenv('GOOGLE_OAUTH_TOKEN_JSON')
    if not token_json:
        print("❌ No GOOGLE_OAUTH_TOKEN_JSON found")
        return False

    try:
        # Decode the token
        if token_json.startswith('ey'):  # Base64 encoded
            token_data = json.loads(base64.b64decode(token_json).decode())
        else:  # Plain JSON
            token_data = json.loads(token_json)

        print(f"🔍 Current token type: {token_data.get('type', 'unknown')}")
        print(f"🔍 Has refresh token: {'refresh_token' in token_data}")

        # Create credentials object
        creds = Credentials.from_authorized_user_info(token_data)

        if not creds.refresh_token:
            print("❌ No refresh token available - need to re-authorize")
            return False

        # Attempt refresh
        print("🔄 Attempting token refresh...")
        creds.refresh(Request())

        # Save refreshed token
        refreshed_data = {
            'token': creds.token,
            'refresh_token': creds.refresh_token,
            'token_uri': creds.token_uri,
            'client_id': creds.client_id,
            'client_secret': creds.client_secret,
            'scopes': creds.scopes,
            'type': 'authorized_user'
        }

        # Encode as base64
        refreshed_json = json.dumps(refreshed_data)
        refreshed_b64 = base64.b64encode(refreshed_json.encode()).decode()

        print("✅ Token refreshed successfully!")
        print(f"🔑 New token (copy to Railway):")
        print(refreshed_b64)

        return True

    except Exception as e:
        print(f"❌ Failed to refresh token: {e}")
        print("💡 You'll need to re-authorize with fresh OAuth flow")
        return False

if __name__ == "__main__":
    refresh_oauth_token()