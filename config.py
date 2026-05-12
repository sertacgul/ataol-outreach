import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent


class Config:
    # Paths
    DATABASE_PATH = BASE_DIR / os.getenv("DATABASE_PATH", "data/ataol.db")

    # API Keys
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

    # Gmail
    GMAIL_SENDER_EMAIL = os.getenv("GMAIL_SENDER_EMAIL", "sertacgul@strategythrust.com")
    GMAIL_CREDENTIALS_PATH = BASE_DIR / os.getenv("GMAIL_CREDENTIALS_PATH", "gmail_auth/credentials.json")
    GMAIL_TOKEN_PATH = BASE_DIR / os.getenv("GMAIL_TOKEN_PATH", "gmail_auth/token.json")

    # Limits
    MAX_EMAILS_PER_DAY = int(os.getenv("MAX_EMAILS_PER_DAY", "25"))
    SCRAPE_DELAY_SECONDS = float(os.getenv("SCRAPE_DELAY_SECONDS", "2"))

    # Flask
    FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-me")
    FLASK_PORT = int(os.getenv("FLASK_PORT", "5001"))

    # Gemini
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    GEMINI_CALL_DELAY = float(os.getenv("GEMINI_CALL_DELAY", "2"))
    GEMINI_RETRY_MAX = int(os.getenv("GEMINI_RETRY_MAX", "3"))
    GEMINI_RETRY_BACKOFF = float(os.getenv("GEMINI_RETRY_BACKOFF", "2.0"))

    # Notifications
    NOTIFICATION_EMAIL = os.getenv("NOTIFICATION_EMAIL", "sertacgul@strategythrust.com")

    # Branding
    PLATFORM_NAME = "ATAOL AI Techs"
    ATAOL_URL = "https://www.ataolai.tech"
    STRATEGYTHRUST_URL = "https://strategythrust.com"
    ACTLEDGER_URL = "https://actledger.com"
