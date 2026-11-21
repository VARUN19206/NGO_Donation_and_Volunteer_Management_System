"""Creates the database, the tables, then adds demo accounts and sample campaigns.

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


SAMPLE_CAMPAIGNS = [
    ("Education Support", "education", 150000,
     "Help children from low-income families continue their schooling. Funds will go towards books, uniforms, school fees and learning materials.\n\nEvery contribution helps a child stay in the classroom."),
    ("Food Distribution", "food", 80000,
     "Provide nutritious meals to families who struggle to afford daily food. The campaign supports weekly food packets and community meal events.\n\nNo family should go to bed hungry."),
    ("Medical Camp", "health", 120000,
     "Organise free health check-up camps in rural areas, with basic tests, doctor consultations and essential medicines for people who cannot afford care."),
]


def add_sample_campaigns():
    """Adds 3 sample campaigns (only when there are none) owned by the demo campaign admin."""
    conn = db.connect()
    added = 0
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM campaigns")
            if cur.fetchone()["n"]:
                return 0
            cur.execute("SELECT user_id FROM users WHERE email = %s", ("campaign.admin@example.com",))
            owner = cur.fetchone()
            if not owner:
                return 0
            for title, cat, goal, desc in SAMPLE_CAMPAIGNS:
                cur.execute(
                    "INSERT INTO campaigns (title, description, category, goal_amount, created_by) "
                    "VALUES (%s, %s, %s, %s, %s)", (title, desc, cat, goal, owner["user_id"]))
                added += 1
    finally:
        conn.close()
    return added


SAMPLE_TASKS = [
    ("Food Distribution", "Pack and hand out food packets",
     "Help pack the weekly food packets and hand them out to the registered families.", "pending"),
    ("Education Support", "Sort donated books and uniforms",
     "Sort the donated books and uniforms by class and make a simple list for the school.", "in_progress"),
]


def add_sample_tasks():
    """Adds 2 sample tasks for the demo volunteer (only when there are no tasks)."""
    conn = db.connect()
    added = 0
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM tasks")
            if cur.fetchone()["n"]:
                return 0
            cur.execute("SELECT user_id FROM users WHERE email = %s", ("volunteer@example.com",))
            vol = cur.fetchone()
            cur.execute("SELECT user_id FROM users WHERE email = %s", ("campaign.admin@example.com",))
            admin = cur.fetchone()
            if not vol or not admin:
                return 0
            for campaign_title, title, desc, status in SAMPLE_TASKS:
                cur.execute("SELECT campaign_id FROM campaigns WHERE title = %s", (campaign_title,))
                camp = cur.fetchone()
                if not camp:
                    continue
                cur.execute(
                    "INSERT INTO tasks (campaign_id, title, description, assigned_to, status, created_by) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (camp["campaign_id"], title, desc, vol["user_id"], status, admin["user_id"]))
                added += 1
    finally:
        conn.close()
    return added


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

    print(f"Database '{config.DB_NAME}' and all tables are ready.")
    if "--no-demo" not in sys.argv:
        added = add_demo_users()
        print(f"Demo accounts added: {added} (password for all: {DEMO_PASSWORD})")
        for name, email, role in DEMO_USERS:
            print(f"  {config.ROLE_LABELS[role]:<15} {email}")
        print("Demo accounts are only for testing. Remove them before real use.")
        print(f"Sample campaigns added: {add_sample_campaigns()}")
        print(f"Sample volunteer tasks added: {add_sample_tasks()}")
