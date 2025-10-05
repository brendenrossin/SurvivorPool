#!/usr/bin/env python3
"""
Proactive OAuth Token Refresh Job
Runs periodically to keep the OAuth token fresh and prevent revocation
"""

import os
import sys
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.oauth_manager import OAuthTokenManager

def main():
    """Proactively refresh OAuth token to prevent expiration"""
    print(f"🔄 Starting OAuth token refresh at {datetime.now()}")

    manager = OAuthTokenManager()

    # Try to ensure valid token (will refresh if needed)
    success = manager.ensure_valid_token()

    if success:
        print("✅ OAuth token is valid and fresh")

        # If token was refreshed, save it for manual Railway update
        if manager.token_updated:
            print("🔑 Token was refreshed - updating saved credentials")
            manager.save_refreshed_token_locally()
            print("")
            print("⚠️  IMPORTANT: Token was refreshed!")
            print("   The refreshed token has been saved locally, but Railway")
            print("   environment variables are immutable from within the app.")
            print("")
            print("   📋 TODO: Update Railway GOOGLE_OAUTH_TOKEN_JSON variable")
            print("      with the new token from .credentials/.railway_oauth_token_refreshed.txt")
            print("")
            print("   This is a manual step to prevent unauthorized credential updates.")

        return True
    else:
        print("❌ Failed to refresh OAuth token")
        print("💡 This usually means the refresh token has been revoked")
        print("   Manual re-authorization is required:")
        print("   1. Run: python scripts/testing/test_personal_sheets.py")
        print("   2. Follow browser authentication flow")
        print("   3. Update Railway GOOGLE_OAUTH_TOKEN_JSON variable")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
