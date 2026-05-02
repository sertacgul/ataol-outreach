import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from config import Config

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


def get_gmail_service():
    """Get authenticated Gmail API service."""
    creds = None
    token_path = str(Config.GMAIL_TOKEN_PATH)
    creds_path = str(Config.GMAIL_CREDENTIALS_PATH)

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(creds_path):
                raise FileNotFoundError(
                    f"Gmail credentials not found at {creds_path}. "
                    "Download OAuth 2.0 Client ID from Google Cloud Console "
                    "and save as gmail_auth/credentials.json"
                )
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(token_path, "w") as token:
            token.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)
