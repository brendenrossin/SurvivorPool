#!/usr/bin/env python3
"""
OAuth Token Manager with Auto-Refresh
Handles Google OAuth tokens with automatic refresh capability
"""

import os
import json
import base64
from datetime import datetime, timezone
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError

class OAuthTokenManager:
    """Manages OAuth tokens with auto-refresh"""

    def __init__(self):
        self.creds = None
        self.token_updated = False

    def load_credentials(self) -> bool:
        """Load credentials from environment variable"""
        try:
            token_json = os.getenv('GOOGLE_OAUTH_TOKEN_JSON')
            if not token_json:
                print("❌ No GOOGLE_OAUTH_TOKEN_JSON environment variable found")
                return False

            # Handle both base64 and plain JSON formats
            try:
                if token_json.startswith('ey'):  # Base64 encoded
                    token_data = json.loads(base64.b64decode(token_json).decode())
                else:  # Plain JSON
                    token_data = json.loads(token_json)
            except Exception as e:
                print(f"❌ Failed to parse token JSON: {e}")
                return False

            # Create credentials object
            self.creds = Credentials.from_authorized_user_info(token_data)
            print("✅ OAuth credentials loaded successfully")
            return True

        except Exception as e:
            print(f"❌ Failed to load credentials: {e}")
            return False

    def ensure_valid_token(self) -> bool:
        """Ensure we have a valid access token, refreshing if needed"""
        if not self.creds:
            if not self.load_credentials():
                return False

        # Check if token needs refresh
        if not self.creds.valid:
            if self.creds.expired and self.creds.refresh_token:
                try:
                    print("🔄 Access token expired, attempting refresh...")
                    self.creds.refresh(Request())
                    self.token_updated = True
                    print("✅ Token refreshed successfully")

                    # Log the new expiry for debugging
                    if hasattr(self.creds, 'expiry') and self.creds.expiry:
                        expiry_str = self.creds.expiry.strftime("%Y-%m-%d %H:%M:%S UTC")
                        print(f"🕒 New token expires: {expiry_str}")

                    return True

                except RefreshError as e:
                    print(f"❌ Failed to refresh token: {e}")
                    print("💡 Token may be permanently expired - manual re-authorization needed")
                    return False
                except Exception as e:
                    print(f"❌ Unexpected error during token refresh: {e}")
                    return False
            else:
                print("❌ Token invalid and no refresh token available")
                return False

        print("✅ Token is valid")
        return True

    def get_credentials(self) -> Credentials:
        """Get valid credentials, refreshing if necessary"""
        if self.ensure_valid_token():
            return self.creds
        return None

    def get_updated_token_for_railway(self) -> str:
        """Get base64-encoded token for updating Railway environment"""
        if not self.creds:
            return None

        # Convert credentials back to JSON format
        token_data = {
            'token': self.creds.token,
            'refresh_token': self.creds.refresh_token,
            'token_uri': self.creds.token_uri,
            'client_id': self.creds.client_id,
            'client_secret': self.creds.client_secret,
            'scopes': self.creds.scopes,
            'type': 'authorized_user'
        }

        # Add expiry if available
        if hasattr(self.creds, 'expiry') and self.creds.expiry:
            token_data['expiry'] = self.creds.expiry.isoformat()

        # Encode as base64
        token_json = json.dumps(token_data)
        return base64.b64encode(token_json.encode()).decode()

    def save_refreshed_token_locally(self):
        """Save refreshed token to local file for Railway update"""
        if not self.token_updated or not self.creds:
            return

        try:
            refreshed_token = self.get_updated_token_for_railway()

            with open('.credentials/.railway_oauth_token_refreshed.txt', 'w') as f:
                f.write(refreshed_token)

            print("💾 Refreshed token saved to .credentials/.railway_oauth_token_refreshed.txt")
            print("🔄 Update Railway GOOGLE_OAUTH_TOKEN_JSON with this new value")

        except Exception as e:
            print(f"⚠️ Failed to save refreshed token: {e}")

# Convenience function for easy import
def get_oauth_credentials():
    """Get valid OAuth credentials with auto-refresh"""
    manager = OAuthTokenManager()
    creds = manager.get_credentials()

    # Save refreshed token if it was updated
    if manager.token_updated:
        manager.save_refreshed_token_locally()

    return creds