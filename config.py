"""Settings are read from the .env file (see .env.example)."""
import os
import secrets

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
