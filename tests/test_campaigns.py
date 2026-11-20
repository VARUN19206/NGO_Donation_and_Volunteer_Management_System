"""Module 2 tests (home page, campaign list/details, create/edit and permissions).

Use a test database:  DB_NAME=ngo_donation_test python -m unittest discover -s tests -v
"""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DB_NAME", "ngo_donation_test")

from werkzeug.security import generate_password_hash  # noqa: E402

import db  # noqa: E402
from app import create_app  # noqa: E402
from campaigns import inr  # noqa: E402

PASSWORD = "Demo@1234"
OTHER_ADMIN = "other.admin@t.example"


def sql(statement, params=()):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(statement, params)
            return cur.fetchall()
    finally:
        conn.close()


class CampaignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if "test" not in os.environ["DB_NAME"]:
            raise RuntimeError("Tests must run on a database whose name contains 'test'.")

    def setUp(self):
        self.cleanup()
        sql("INSERT INTO users (full_name, email, password_hash, role) VALUES (%s,%s,%s,'campaign_admin')",
            ("Other Admin", OTHER_ADMIN, generate_password_hash(PASSWORD, method="pbkdf2:sha256")))
        self.client = create_app().test_client()

    def tearDown(self):
        self.cleanup()

    def cleanup(self):
        sql("DELETE FROM donations WHERE campaign_id IN "
            "(SELECT campaign_id FROM (SELECT campaign_id FROM campaigns WHERE title LIKE %s) x)", ("TEST %",))
        sql("DELETE FROM campaigns WHERE title LIKE %s", ("TEST %",))
        sql("DELETE FROM users WHERE email = %s", (OTHER_ADMIN,))

    # helpers
    def token(self, path):
        html = self.client.get(path).get_data(as_text=True)
        return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)

    def login(self, email, tab):
        self.client = create_app().test_client()
        r = self.client.post("/login", data={"email": email, "password": PASSWORD, "role": tab,
                                             "csrf_token": self.token("/login")})
        self.assertEqual(r.status_code, 302)

    def post_campaign(self, path, **over):
        data = {"title": "TEST Clean Water", "category": "health", "goal_amount": "25000",
                "description": "Dig wells and install filters for villages without safe drinking water.",
                "status": "active"}
        data.update(over)
        data["csrf_token"] = self.token(path)
        return self.client.post(path, data=data)

    def make_campaign(self, **over):
        self.login("campaign.admin@example.com", "admin")
        self.post_campaign("/manage/campaigns/new", **over)
        row = sql("SELECT campaign_id FROM campaigns WHERE title = %s", (over.get("title", "TEST Clean Water"),))
        return row[0]["campaign_id"]

    # -- public pages --
    def test_home_page_is_public_and_shows_real_campaigns(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        page = r.get_data(as_text=True)
        self.assertIn("Together We", page)
        self.assertIn("Our Ongoing Campaigns", page)
        self.assertIn("Education Support", page)

    def test_stats_are_live_counts(self):
        page = self.client.get("/").get_data(as_text=True)
        n = sql("SELECT COUNT(*) AS n FROM campaigns WHERE status='active'")[0]["n"]
        self.assertRegex(page, r"<strong>%d</strong><span>Active Campaigns" % n)

    def test_campaign_list_and_details(self):
        self.assertEqual(self.client.get("/campaigns").status_code, 200)
        cid = sql("SELECT campaign_id FROM campaigns WHERE title='Education Support'")[0]["campaign_id"]
        page = self.client.get(f"/campaigns/{cid}").get_data(as_text=True)
        self.assertIn("About this campaign", page)
        self.assertIn("books, uniforms", page)
        self.assertIn("₹1,50,000", page)

    def test_unknown_campaign_is_404(self):
        self.assertEqual(self.client.get("/campaigns/99999999").status_code, 404)

    def test_inr_format(self):
        self.assertEqual(inr(500), "₹500")
        self.assertEqual(inr(150000), "₹1,50,000")
        self.assertEqual(inr(12345678), "₹1,23,45,678")
        self.assertEqual(inr("2500.50"), "₹2,500.50")

    # -- create / edit --
    def test_campaign_admin_can_create(self):
        self.login("campaign.admin@example.com", "admin")
        r = self.post_campaign("/manage/campaigns/new")
        self.assertEqual(r.status_code, 302)
        self.assertIn("TEST Clean Water", self.client.get("/campaigns").get_data(as_text=True))

    def test_invalid_campaign_rejected(self):
        self.login("campaign.admin@example.com", "admin")
        bad = [dict(title="ab"), dict(description="too short"), dict(goal_amount="0"),
               dict(goal_amount="abc"), dict(goal_amount="NaN"), dict(goal_amount="-5"),
               dict(goal_amount="1000000000"), dict(category="nonsense")]
        for over in bad:
            r = self.post_campaign("/manage/campaigns/new", **over)
            self.assertEqual(r.status_code, 400, over)

    def test_donor_and_volunteer_cannot_manage(self):
        for email, tab in (("donor@example.com", "donor"), ("volunteer@example.com", "volunteer")):
            self.login(email, tab)
            for path in ("/manage/campaigns", "/manage/campaigns/new"):
                r = self.client.get(path)
                self.assertEqual(r.status_code, 302, (email, path))
                self.assertNotIn("/manage", r.headers["Location"])
            self.assertEqual(self.client.post("/manage/campaigns/new", data={}).status_code, 400)  # CSRF

    def test_logged_out_cannot_manage(self):
        for path in ("/manage/campaigns", "/manage/campaigns/new"):
            r = self.client.get(path)
            self.assertEqual(r.status_code, 302)
            self.assertIn("/login", r.headers["Location"])

    def test_edit_own_campaign(self):
        cid = self.make_campaign()
        r = self.post_campaign(f"/manage/campaigns/{cid}/edit", title="TEST Clean Water Updated", goal_amount="30000")
        self.assertEqual(r.status_code, 302)
        row = sql("SELECT title, goal_amount FROM campaigns WHERE campaign_id=%s", (cid,))[0]
        self.assertEqual(row["title"], "TEST Clean Water Updated")
        self.assertEqual(int(row["goal_amount"]), 30000)

    def test_campaign_admin_cannot_edit_someone_elses(self):
        cid = self.make_campaign()
        self.login(OTHER_ADMIN, "admin")
        self.assertEqual(self.client.get(f"/manage/campaigns/{cid}/edit").status_code, 302)
        # A forged POST with a valid token (taken from a page this admin can open) must still fail.
        r = self.client.post(f"/manage/campaigns/{cid}/edit", data={
            "title": "TEST Hijacked", "category": "health", "goal_amount": "1",
            "description": "Trying to change a campaign that belongs to someone else.",
            "status": "active", "csrf_token": self.token("/manage/campaigns")})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(sql("SELECT title FROM campaigns WHERE campaign_id=%s", (cid,))[0]["title"], "TEST Clean Water")

    def test_other_admin_does_not_see_it_in_manage_list(self):
        self.make_campaign()
        self.login(OTHER_ADMIN, "admin")
        self.assertNotIn("TEST Clean Water", self.client.get("/manage/campaigns").get_data(as_text=True))

    def test_platform_admin_can_edit_any(self):
        cid = self.make_campaign()
        self.login("platform.admin@example.com", "admin")
        self.assertIn("TEST Clean Water", self.client.get("/manage/campaigns").get_data(as_text=True))
        r = self.post_campaign(f"/manage/campaigns/{cid}/edit", title="TEST By Platform Admin")
        self.assertEqual(r.status_code, 302)
        self.assertEqual(sql("SELECT title FROM campaigns WHERE campaign_id=%s", (cid,))[0]["title"], "TEST By Platform Admin")

    def test_closed_campaign_hidden_from_list_but_details_open(self):
        cid = self.make_campaign()
        self.post_campaign(f"/manage/campaigns/{cid}/edit", status="closed")
        public = create_app().test_client()
        self.assertNotIn("TEST Clean Water", public.get("/campaigns").get_data(as_text=True))
        self.assertNotIn("TEST Clean Water", public.get("/").get_data(as_text=True))
        page = public.get(f"/campaigns/{cid}").get_data(as_text=True)
        self.assertIn("TEST Clean Water", page)
        self.assertIn("Closed", page)

    def test_edit_button_only_for_allowed_users(self):
        cid = self.make_campaign()
        public = create_app().test_client().get(f"/campaigns/{cid}").get_data(as_text=True)
        self.assertNotIn("Edit campaign", public)
        self.assertIn("Edit campaign", self.client.get(f"/campaigns/{cid}").get_data(as_text=True))
        self.login(OTHER_ADMIN, "admin")
        self.assertNotIn("Edit campaign", self.client.get(f"/campaigns/{cid}").get_data(as_text=True))

    def test_text_is_escaped(self):
        cid = self.make_campaign(title="TEST <script>alert(1)</script>",
                                 description="<img src=x onerror=alert(1)> padding padding padding")
        page = self.client.get(f"/campaigns/{cid}").get_data(as_text=True)
        self.assertNotIn("<script>alert(1)</script>", page)
        self.assertNotIn("<img src=x", page)
        self.assertIn("&lt;script&gt;", page)

    def test_edit_unknown_campaign_404(self):
        self.login("campaign.admin@example.com", "admin")
        self.assertEqual(self.client.get("/manage/campaigns/99999999/edit").status_code, 404)


if __name__ == "__main__":
    unittest.main()
