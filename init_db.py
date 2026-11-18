"""Creates the database and the users table, then adds 4 demo accounts.

Run once:   python init_db.py
Skip demo:  python init_db.py --no-demo
"""
import sys
from pathlib import Path

from werkzeug.security import generate_password_hash

import config
import db

DEMO_PASSWORD = "Demo@1234"
DEMO_USERS = [
    ("Demo Donor", "donor@example.com", "donor"),
    ("Demo Volunteer", "volunteer@example.com", "volunteer"),
    ("Demo Campaign Admin", "campaign.admin@example.com", "campaign_admin"),
    ("Demo Platform Admin", "platform.admin@example.com", "platform_admin"),
]


def run_schema():
    sql = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
    sql = sql.replace("ngo_donation_db", config.DB_NAME)
    # remove "-- comment" lines, then run each statement
    lines = [ln for ln in sql.splitlines() if not ln.strip().startswith("--")]
    statements = [s.strip() for s in "\n".join(lines).split(";") if s.strip()]
    conn = db.connect(database=None)
    try:
        with conn.cursor() as cur:
            for stmt in statements:
                cur.execute(stmt)
    finally:
        conn.close()


def add_demo_users():
    conn = db.connect()
    added = 0
    try:
        with conn.cursor() as cur:
            for name, email, role in DEMO_USERS:
                cur.execute("SELECT user_id FROM users WHERE email = %s", (email,))
                if cur.fetchone():
                    continue
                cur.execute(
                    "INSERT INTO users (full_name, email, password_hash, role) "
                    "VALUES (%s, %s, %s, %s)",
                    (name, email, generate_password_hash(DEMO_PASSWORD, method="pbkdf2:sha256"), role),
                )
                added += 1
    finally:
        conn.close()
    return added


if __name__ == "__main__":
    try:
        run_schema()
    except Exception as exc:  # noqa: BLE001 - show a friendly message
        print("\nCould not set up the database.")
        print(f"Reason: {exc}")
        print("Check that MySQL is running and that DB_USER / DB_PASSWORD in .env are correct.")
        sys.exit(1)

    print(f"Database '{config.DB_NAME}' and table 'users' are ready.")
    if "--no-demo" not in sys.argv:
        added = add_demo_users()
        print(f"Demo accounts added: {added} (password for all: {DEMO_PASSWORD})")
        for name, email, role in DEMO_USERS:
            print(f"  {config.ROLE_LABELS[role]:<15} {email}")
        print("Demo accounts are only for testing. Remove them before real use.")
