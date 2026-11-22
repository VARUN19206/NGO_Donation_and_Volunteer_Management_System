"""Module 5 tests: user management, donation records, reports and CSV exports."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _env  # noqa: F401,E402
from test_module4 import Base, TITLE, OTHER_ADMIN, VOL2, DONOR2, sql, PASSWORD  # noqa: E402
from app import create_app  # noqa: E402


class AdminTests(Base):
    def as_platform(self):
        self.as_admin("platform.admin@example.com")

    def set_active(self, email, value):
        uid = sql("SELECT user_id FROM users WHERE email=%s", (email,))[0]["user_id"]
        return self.client.post(f"/admin/users/{uid}/active",
                                data={"active": value, "csrf_token": self.token("/admin/users")})

    def active(self, email):
        return sql("SELECT is_active FROM users WHERE email=%s", (email,))[0]["is_active"]

    # -- users --
    def test_platform_admin_lists_users(self):
        self.as_platform()
        html = self.client.get("/admin/users").get_data(as_text=True)
        self.assertIn(DONOR2, html)
        self.assertIn("donor@example.com", html)
        only = self.client.get("/admin/users?role=volunteer").get_data(as_text=True)
        self.assertIn(VOL2, only)
        self.assertNotIn(DONOR2, only)

    def test_deactivate_blocks_login_and_session(self):
        self.as_donor(DONOR2)
        self.as_platform()
        self.assertEqual(self.set_active(DONOR2, "0").status_code, 302)
        self.assertEqual(self.active(DONOR2), 0)
        # cannot log in
        r = self.login(DONOR2, "donor")
        self.assertNotIn("/donor", r.headers.get("Location", ""))
        self.as_platform()
        self.set_active(DONOR2, "1")
        self.assertEqual(self.active(DONOR2), 1)
        self.login(DONOR2, "donor")
        self.assertEqual(self.client.get("/donor").status_code, 200)

    def test_existing_session_stops_working_after_deactivation(self):
        donor_client = create_app().test_client()
        import re
        html = donor_client.get("/login").get_data(as_text=True)
        tok = re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)
        donor_client.post("/login", data={"email": DONOR2, "password": PASSWORD, "role": "donor", "csrf_token": tok})
        self.assertEqual(donor_client.get("/donor").status_code, 200)
        sql("UPDATE users SET is_active=0 WHERE email=%s", (DONOR2,))
        self.assertNotEqual(donor_client.get("/donor").status_code, 200)

    def test_cannot_deactivate_self_or_platform_admin(self):
        self.as_platform()
        self.set_active("platform.admin@example.com", "0")
        self.assertEqual(self.active("platform.admin@example.com"), 1)

    def test_user_pages_are_platform_admin_only(self):
        for login in (lambda: self.as_donor(), lambda: self.as_volunteer(), lambda: self.as_admin()):
            login()
            self.assertNotEqual(self.client.get("/admin/users").status_code, 200)
        self.client = create_app().test_client()
        self.assertEqual(self.client.get("/admin/users").status_code, 302)
        self.as_admin()
        uid = sql("SELECT user_id FROM users WHERE email=%s", (DONOR2,))[0]["user_id"]
        r = self.client.post(f"/admin/users/{uid}/active",
                             data={"active": "0", "csrf_token": self.token("/admin")})
        self.assertNotEqual(r.status_code, 200)
        self.assertEqual(self.active(DONOR2), 1)

    def test_set_active_needs_csrf(self):
        self.as_platform()
        uid = sql("SELECT user_id FROM users WHERE email=%s", (DONOR2,))[0]["user_id"]
        self.assertEqual(self.client.post(f"/admin/users/{uid}/active", data={"active": "0"}).status_code, 400)
        self.assertEqual(self.active(DONOR2), 1)

    # -- donation records / reports --
    def seed(self):
        self.as_donor(DONOR2)
        self.donate("700")
        self.as_donor()
        self.donate("300")

    def test_owner_sees_own_campaign_donations(self):
        self.seed()
        self.as_admin()
        html = self.client.get("/admin/donations").get_data(as_text=True)
        self.assertIn(TITLE, html)
        self.assertIn(DONOR2, html)
        self.assertIn("₹1,000", html)

    def test_other_campaign_admin_sees_nothing_of_mine(self):
        self.seed()
        self.as_admin(OTHER_ADMIN)
        self.assertNotIn(TITLE, self.client.get("/admin/donations").get_data(as_text=True))
        self.assertNotIn(DONOR2, self.client.get("/admin/donations.csv").get_data(as_text=True))
        self.assertNotIn(TITLE, self.client.get("/admin/reports").get_data(as_text=True))
        # asking for someone else's campaign id is ignored
        self.assertNotIn(TITLE, self.client.get(f"/admin/donations?campaign={self.cid}").get_data(as_text=True))

    def test_platform_admin_sees_all(self):
        self.seed()
        self.as_platform()
        self.assertIn(TITLE, self.client.get("/admin/donations").get_data(as_text=True))
        self.assertIn(TITLE, self.client.get(f"/admin/donations?campaign={self.cid}").get_data(as_text=True))

    def test_report_numbers(self):
        self.seed()
        sql("INSERT INTO tasks (campaign_id, title, description, assigned_to, status, created_by) "
            "VALUES (%s,'t1','Task one description',%s,'completed',%s),(%s,'t2','Task two description',%s,'pending',%s)",
            (self.cid, self.vol, self.owner, self.cid, self.vol, self.owner))
        self.as_admin()
        csv_text = self.client.get("/admin/reports.csv").get_data(as_text=True)
        line = [l for l in csv_text.splitlines() if l.startswith(TITLE)][0]
        self.assertEqual(line, f"{TITLE},active,5000.00,1000.00,2,2,1")
        self.assertIn("₹1,000", self.client.get("/admin/reports").get_data(as_text=True))

    def test_csv_downloads_and_formula_injection_guard(self):
        sql("UPDATE campaigns SET title=%s WHERE campaign_id=%s", ("=HYPERLINK(1)", self.cid))
        try:
            self.seed_for_title()
            self.as_admin()
            r = self.client.get("/admin/donations.csv")
            self.assertEqual(r.mimetype, "text/csv")
            self.assertIn("attachment", r.headers["Content-Disposition"])
            body = r.get_data(as_text=True)
            self.assertIn("'=HYPERLINK(1)", body)
            self.assertNotIn(",=HYPERLINK", body)
        finally:
            sql("DELETE FROM donations WHERE campaign_id=%s", (self.cid,))
            sql("UPDATE campaigns SET title=%s WHERE campaign_id=%s", (TITLE, self.cid))

    def seed_for_title(self):
        self.as_donor()
        self.donate("100")

    def test_csv_requires_admin(self):
        self.as_donor()
        for p in ("/admin/donations.csv", "/admin/reports.csv", "/admin/reports", "/admin/donations"):
            self.assertNotEqual(self.client.get(p).status_code, 200, p)

    def test_dashboards_show_stats(self):
        self.seed()
        self.as_admin()
        self.assertIn("Raised (test)", self.client.get("/admin").get_data(as_text=True))
        self.as_platform()
        html = self.client.get("/admin").get_data(as_text=True)
        self.assertIn("Manage users", html)
        self.assertIn("Manage Users", html)


if __name__ == "__main__":
    unittest.main()
