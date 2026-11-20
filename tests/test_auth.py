"""Module 1 tests. They use a separate database (DB_NAME=ngo_donation_test).

Run:  DB_NAME=ngo_donation_test python init_db.py   (once)
      DB_NAME=ngo_donation_test python -m unittest discover -s tests -v
"""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DB_NAME", "ngo_donation_test")

import db  # noqa: E402
from app import create_app  # noqa: E402

PASSWORD = "Demo@1234"


class AuthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if "test" not in os.environ["DB_NAME"]:
            raise RuntimeError("Tests must run on a database whose name contains 'test'.")

    def setUp(self):
        conn = db.connect()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM donations WHERE donor_id IN (SELECT user_id FROM "
                        "(SELECT user_id FROM users WHERE email LIKE '%@t.example') x)")
            cur.execute("DELETE FROM users WHERE email LIKE '%@t.example'")
        conn.close()
        self.client = create_app().test_client()

    # -- helpers --
    def token(self, path="/login"):
        html = self.client.get(path).get_data(as_text=True)
        return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)

    def register(self, **over):
        data = {"full_name": "Test User", "email": "u1@t.example", "password": PASSWORD,
                "confirm_password": PASSWORD, "role": "donor"}
        data.update(over)
        data["csrf_token"] = self.token("/register")
        return self.client.post("/register", data=data)

    def login(self, email, password=PASSWORD, role="donor"):
        return self.client.post("/login", data={
            "email": email, "password": password, "role": role,
            "csrf_token": self.token("/login")})

    # -- registration --
    def test_register_donor_and_volunteer(self):
        self.assertEqual(self.register(email="d@t.example").status_code, 302)
        self.assertEqual(self.register(email="v@t.example", role="volunteer").status_code, 302)

    def test_password_is_hashed(self):
        self.register(email="h@t.example")
        row = db.connect().cursor()
        conn = db.connect()
        with conn.cursor() as cur:
            cur.execute("SELECT password_hash FROM users WHERE email='h@t.example'")
            stored = cur.fetchone()["password_hash"]
        conn.close()
        self.assertNotIn(PASSWORD, stored)
        self.assertTrue(stored.startswith("pbkdf2:sha256:"))

    def test_duplicate_email_rejected(self):
        self.register(email="dup@t.example")
        r = self.register(email="dup@t.example")
        self.assertEqual(r.status_code, 400)
        self.assertIn("already exists", r.get_data(as_text=True))

    def test_weak_password_rejected(self):
        for pw in ("short1", "onlyletters", "12345678"):
            r = self.register(email="w@t.example", password=pw, confirm_password=pw)
            self.assertEqual(r.status_code, 400, pw)

    def test_password_mismatch_rejected(self):
        self.assertEqual(self.register(email="m@t.example", confirm_password="Other@1234").status_code, 400)

    def test_cannot_register_as_admin(self):
        for role in ("platform_admin", "campaign_admin", "admin"):
            self.assertEqual(self.register(email="a@t.example", role=role).status_code, 400, role)

    def test_invalid_email_rejected(self):
        self.assertEqual(self.register(email="not-an-email").status_code, 400)

    # -- login / roles --
    def test_login_each_role_goes_to_own_dashboard(self):
        cases = [("donor@example.com", "donor", "/donor"),
                 ("volunteer@example.com", "volunteer", "/volunteer"),
                 ("campaign.admin@example.com", "admin", "/admin"),
                 ("platform.admin@example.com", "admin", "/admin")]
        for email, tab, path in cases:
            client = create_app().test_client()
            self.client = client
            r = self.login(email, role=tab)
            self.assertEqual(r.status_code, 302, email)
            self.assertTrue(r.headers["Location"].endswith(path), email)
            self.assertEqual(client.get(path).status_code, 200, email)

    def test_wrong_tab_rejected(self):
        self.assertEqual(self.login("donor@example.com", role="admin").status_code, 401)
        self.assertEqual(self.login("platform.admin@example.com", role="donor").status_code, 401)

    def test_wrong_password_and_unknown_email_same_message(self):
        a = self.login("donor@example.com", password="Wrong@1234").get_data(as_text=True)
        b = self.login("nobody@example.com").get_data(as_text=True)
        msg = "Invalid email or password for the selected role."
        self.assertIn(msg, a)
        self.assertIn(msg, b)

    def test_new_user_can_login_after_register(self):
        self.register(email="n@t.example", full_name="New Person")
        self.assertEqual(self.login("n@t.example").status_code, 302)
        page = self.client.get("/donor").get_data(as_text=True)
        self.assertIn("New Person", page)

    # -- access control --
    def test_dashboards_need_login(self):
        for path in ("/donor", "/volunteer", "/admin"):
            r = self.client.get(path)
            self.assertEqual(r.status_code, 302, path)
            self.assertIn("/login", r.headers["Location"])

    def test_role_cannot_open_other_dashboard(self):
        self.login("donor@example.com")
        r = self.client.get("/admin")
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r.headers["Location"].endswith("/donor"))
        r = self.client.get("/volunteer")
        self.assertTrue(r.headers["Location"].endswith("/donor"))

    def test_logout_ends_session(self):
        self.login("donor@example.com")
        r = self.client.post("/logout", data={"csrf_token": self.token("/donor")})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.client.get("/donor").status_code, 302)

    def test_logout_requires_post(self):
        self.assertEqual(self.client.get("/logout").status_code, 405)

    def test_csrf_required(self):
        r = self.client.post("/login", data={"email": "donor@example.com", "password": PASSWORD, "role": "donor"})
        self.assertEqual(r.status_code, 400)

    def test_sql_injection_text_is_harmless(self):
        r = self.login("' OR '1'='1' -- ", password="x")
        self.assertEqual(r.status_code, 401)


if __name__ == "__main__":
    unittest.main()
