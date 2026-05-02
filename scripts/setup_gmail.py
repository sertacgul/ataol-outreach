"""
Setup Gmail OAuth2 credentials.
Run this once to authorize Gmail API access.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gmail_auth.auth import get_gmail_service

if __name__ == "__main__":
    print("Setting up Gmail OAuth2...")
    print("A browser window will open for authorization.\n")
    service = get_gmail_service()
    print("\nGmail setup complete! Token saved.")
