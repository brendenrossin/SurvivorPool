#!/usr/bin/env python3
"""
OAuth Token Manager with Auto-Refresh
Handles Google OAuth tokens with automatic refresh capability
Persists refreshed tokens to PostgreSQL to survive Railway container restarts
"""

import os
import json
import base64
from datetime import datetime, timezone
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError
from sqlalchemy.orm import Session

class OAuthTokenManager:
    """Manages OAuth tokens with auto-refresh"""

    def __init__(self):
        self.creds = None
        self.token_updated = False

    def load_credentials(self) -> bool:
        """Load credentials from database (priority) or environment variable"""
        try:
            token_json = None
            token_source = None

            # PRIORITY 1: Check database for previously refreshed token
            # This persists across Railway container restarts (unlike files)
            try:
                from api.database import SessionLocal
                from api.models import JobMeta

                db = SessionLocal()
                try:
                    job_meta = db.query(JobMeta).filter(JobMeta.job_name == 'oauth_token').first()
                    if job_meta and job_meta.message:
                        token_json = job_meta.message
                        token_source = "database (persisted)"
                        print("🔄 Using previously refreshed OAuth token from database")
                finally:
                    db.close()
            except Exception as e:
                print(f"⚠️ Failed to read token from database: {e}")
                # Fall through to environment variable

            # PRIORITY 2: Fall back to environment variable
            if not token_json:
                token_json = os.getenv('GOOGLE_OAUTH_TOKEN_JSON')
                token_source = "environment variable"
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
            print(f"✅ OAuth credentials loaded successfully from {token_source}")
            return True

        except Exception as e:
            print(f"❌ Failed to load credentials: {e}")
            return False

    def ensure_valid_token(self) -> bool:
        """Ensure we have a valid access token, refreshing if needed"""
        if not self.creds:
            if not self.load_credentials():
                return False

        # Always try to refresh if we have a refresh token
        # This handles cases where access token is expired but refresh token is still valid
        if self.creds.refresh_token:
            # Check if token is expired or invalid
            if not self.creds.valid or self.creds.expired:
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
            # No refresh token available
            if not self.creds.valid:
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

    def save_refreshed_token_to_database(self):
        """Save refreshed token to database (persists across Railway restarts)"""
        if not self.token_updated or not self.creds:
            return

        try:
            from api.database import SessionLocal
            from api.models import JobMeta
            from datetime import datetime, timezone

            refreshed_token = self.get_updated_token_for_railway()

            db = SessionLocal()
            try:
                # Upsert the refreshed token to database
                job_meta = db.query(JobMeta).filter(JobMeta.job_name == 'oauth_token').first()

                if job_meta:
                    job_meta.message = refreshed_token
                    job_meta.last_success_at = datetime.now(timezone.utc)
                    job_meta.status = 'active'
                else:
                    job_meta = JobMeta(
                        job_name='oauth_token',
                        message=refreshed_token,
                        last_success_at=datetime.now(timezone.utc),
                        status='active'
                    )
                    db.add(job_meta)

                db.commit()
                print("💾 Refreshed token saved to database (persists across Railway restarts)")
                print("✅ Auto-refresh enabled! Token will be automatically used on next cron run")
                print("   (No manual Railway update needed for ~6 months)")
            finally:
                db.close()

        except Exception as e:
            print(f"⚠️ Failed to save refreshed token to database: {e}")

# Convenience function for easy import
def get_oauth_credentials():
    """Get valid OAuth credentials with auto-refresh"""
    manager = OAuthTokenManager()
    creds = manager.get_credentials()

    # Save refreshed token to database if it was updated
    if manager.token_updated:
        manager.save_refreshed_token_to_database()

    return creds