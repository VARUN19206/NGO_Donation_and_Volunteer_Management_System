"""Settings are read from the .env file (see .env.example)."""
import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BRAND_NAME = "NGO Donation and Volunteer Management System"
BRAND_SHORT = "NGO Donation & Volunteer"

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "ngo_donation_db")

# If SECRET_KEY is missing a random one is used (logins reset on every restart).
SECRET_KEY = os.getenv("SECRET_KEY") or secrets.token_hex(32)

# Roles stored in the database -> label shown on screen
ROLE_LABELS = {
    "donor": "Donor",
    "volunteer": "Volunteer",
    "campaign_admin": "Campaign Admin",
    "platform_admin": "Platform Admin",
}

# Which database roles may log in from each tab of the login page
TAB_ROLES = {
    "donor": ("donor",),
    "volunteer": ("volunteer",),
    "admin": ("campaign_admin", "platform_admin"),
}

# Only these roles can create an account themselves.
# Admin accounts are created by the project team (see init_db.py).
SELF_REGISTER_ROLES = ("donor", "volunteer")

# Campaign categories -> label and icon name (see templates/_macros.html)
CATEGORIES = {
    "education": {"label": "Education", "icon": "book"},
    "food": {"label": "Food", "icon": "food"},
    "health": {"label": "Health", "icon": "health"},
    "shelter": {"label": "Shelter", "icon": "home"},
    "other": {"label": "Other", "icon": "heart"},
}
CAMPAIGN_STATUSES = ("active", "closed")

# ---- Task status labels (Module 4) ----
TASK_STATUSES = {"pending": "To do", "in_progress": "In progress", "completed": "Completed"}

# ---- Uploads (photo proof for campaign updates) ----
APP_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR") or APP_DIR / "uploads")
MAX_PHOTO_UPLOAD_BYTES = 8 * 1024 * 1024        # each photo, before it is resized
MAX_PHOTOS_PER_UPDATE = 4

# ---- Email ----
OUTBOX_DIR = Path(os.getenv("OUTBOX_DIR") or APP_DIR / "outbox")
SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "587") or "587")
SMTP_USER = os.getenv("SMTP_USER", "").strip()
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", "").strip() or SMTP_USER or "no-reply@ngo.example"
SMTP_TLS = os.getenv("SMTP_TLS", "true").strip().lower() in ("1", "true", "yes")
BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:5000").rstrip("/")
