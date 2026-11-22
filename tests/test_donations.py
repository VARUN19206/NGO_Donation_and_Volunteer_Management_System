"""Module 3 tests: simulated donations, login redirect, history privacy, progress.

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
from auth import safe_next  # noqa: E402
from donations import new_reference  # noqa: E402

PASSWORD = "Demo@1234"
DONOR2 = "donor2@t.example"
TITLE = "TEST Donation Drive"


def sql(statement, params=()):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(statement, params)
            return cur.fetchall()
    finally:
        conn.close()


class DonationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if "test" not in os.environ["DB_NAME"]:
            raise RuntimeError("Tests must run on a database whose name contains 'test'.")

    def setUp(self):
        self.cleanup()
        owner = sql("SELECT user_id FROM users WHERE email='campaign.admin@example.com'")[0]["user_id"]
        sql("INSERT INTO campaigns (title, description, category, goal_amount, created_by) VALUES (%s,%s,%s,%s,%s)",
            (TITLE, "A test campaign used only by the automated tests of Module 3.", "food", 1000, owner))
        self.cid = sql("SELECT campaign_id FROM campaigns WHERE title=%s", (TITLE,))[0]["campaign_id"]
        sql("INSERT INTO users (full_name, email, password_hash, role) VALUES (%s,%s,%s,'donor')",
            ("Second Donor", DONOR2, generate_password_hash(PASSWORD, method="pbkdf2:sha256")))
        self.client = create_app().test_client()

    def tearDown(self):
        self.cleanup()

    def cleanup(self):
        sql("DELETE FROM donations WHERE campaign_id IN (SELECT campaign_id FROM (SELECT campaign_id FROM campaigns WHERE title=%s) x)", (TITLE,))
        sql("DELETE FROM donations WHERE donor_id IN (SELECT user_id FROM (SELECT user_id FROM users WHERE email=%s) x)", (DONOR2,))
        sql("DELETE FROM campaigns WHERE title=%s", (TITLE,))
        sql("DELETE FROM users WHERE email=%s", (DONOR2,))

    # helpers
    def token(self, path="/login"):
        html = self.client.get(path).get_data(as_text=True)
        return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)

    def login(self, email="donor@example.com", tab="donor", **extra):
        self.client = create_app().test_client()
        data = {"email": email, "password": PASSWORD, "role": tab, "csrf_token": self.token("/login")}
        data.update(extra)
        return self.client.post("/login", data=data)

    def donate(self, amount, cid=None):
        cid = cid or self.cid
        return self.client.post(f"/campaigns/{cid}/donate",
                                data={"amount": amount, "csrf_token": self.token(f"/campaigns/{cid}/donate")})

    def count(self):
        return sql("SELECT COUNT(*) AS n FROM donations WHERE campaign_id=%s", (self.cid,))[0]["n"]

    # -- login redirect --
    def test_logged_out_donate_goes_to_login_then_back(self):
        path = f"/campaigns/{self.cid}/donate"
        r = self.client.get(path)
        self.assertEqual(r.status_code, 302)
        self.assertIn("/login", r.headers["Location"])
        self.assertIn("next=", r.headers["Location"])
        r = self.login(next=path)
        self.assertTrue(r.headers["Location"].endswith(path))
        self.assertEqual(self.client.get(path).status_code, 200)

    def test_next_cannot_redirect_off_site(self):
        for bad in ("//evil.com", "https://evil.com/x", "/\\evil.com", "javascript:alert(1)"):
            self.assertIsNone(safe_next(bad), bad)
        self.assertEqual(safe_next("/campaigns/1/donate"), "/campaigns/1/donate")
        r = self.login(next="//evil.com")
        self.assertTrue(r.headers["Location"].endswith("/donor"))

    # -- donating --
    def test_donor_can_donate_and_sees_confirmation(self):
        self.login()
        r = self.donate("500")
        self.assertEqual(r.status_code, 302)
        row = sql("SELECT * FROM donations WHERE campaign_id=%s", (self.cid,))[0]
        self.assertEqual(int(row["amount"]), 500)
        self.assertRegex(row["transaction_ref"], r"^TEST-[0-9A-F]{10}$")
        page = self.client.get(r.headers["Location"]).get_data(as_text=True)
        self.assertIn("Donation saved", page)
        self.assertIn("Simulated test transaction", page)
        self.assertIn(row["transaction_ref"], page)
        self.assertIn("₹500", page)

    def test_donate_page_says_it_is_simulated(self):
        self.login()
        page = self.client.get(f"/campaigns/{self.cid}/donate").get_data(as_text=True)
        self.assertIn("Simulated test transaction", page)
        self.assertIn("no payment gateway", page.lower())

    def test_invalid_amounts_rejected(self):
        self.login()
        for bad in ("0", "0.50", "-5", "abc", "", "NaN", "1e3", "10000001", "12.345", "1,0,0,x"):
            self.assertEqual(self.donate(bad).status_code, 400, bad)
        self.assertEqual(self.count(), 0)

    def test_decimal_and_comma_amounts_accepted(self):
        self.login()
        self.assertEqual(self.donate("250.50").status_code, 302)
        self.assertEqual(self.donate("749.50").status_code, 302)       # together exactly the 1,000 goal
        self.assertEqual(float(sql("SELECT SUM(amount) s FROM donations WHERE campaign_id=%s", (self.cid,))[0]["s"]), 1000.0)

    def test_comma_amount_accepted(self):
        self.login()
        self.assertEqual(self.donate("1,000").status_code, 302)
        self.assertEqual(float(sql("SELECT amount FROM donations WHERE campaign_id=%s", (self.cid,))[0]["amount"]), 1000.0)

    def test_only_donors_can_donate(self):
        for email, tab in (("volunteer@example.com", "volunteer"),
                           ("campaign.admin@example.com", "admin"),
                           ("platform.admin@example.com", "admin")):
            self.login(email, tab)
            r = self.client.get(f"/campaigns/{self.cid}/donate")
            self.assertEqual(r.status_code, 302, email)
            r = self.client.post(f"/campaigns/{self.cid}/donate",
                                 data={"amount": "100", "csrf_token": self.token("/campaigns")})
            self.assertEqual(r.status_code, 302, email)
        self.assertEqual(self.count(), 0)

    def test_cannot_donate_to_closed_campaign(self):
        sql("UPDATE campaigns SET status='closed' WHERE campaign_id=%s", (self.cid,))
        self.login()
        self.assertEqual(self.client.get(f"/campaigns/{self.cid}/donate").status_code, 302)
        self.assertEqual(self.client.post(f"/campaigns/{self.cid}/donate",
                         data={"amount": "100", "csrf_token": self.token("/campaigns")}).status_code, 302)
        self.assertEqual(self.count(), 0)

    def test_unknown_campaign_404(self):
        self.login()
        self.assertEqual(self.client.get("/campaigns/99999999/donate").status_code, 404)

    def test_csrf_required_for_donation(self):
        self.login()
        r = self.client.post(f"/campaigns/{self.cid}/donate", data={"amount": "100"})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.count(), 0)

    def test_references_are_unique_format(self):
        refs = {new_reference() for _ in range(200)}
        self.assertEqual(len(refs), 200)

    # -- history and privacy --
    def test_history_shows_only_own_donations_and_total(self):
        self.login()
        self.donate("300")
        self.donate("200")
        mine = self.client.get("/donor/donations").get_data(as_text=True)
        self.assertIn(TITLE, mine)
        self.assertIn("₹500", mine)           # total
        self.login(DONOR2, "donor")
        theirs = self.client.get("/donor/donations").get_data(as_text=True)
        self.assertNotIn(TITLE, theirs)
        self.assertIn("You have not made any donations yet", theirs)

    def test_cannot_open_someone_elses_confirmation(self):
        self.login()
        r = self.donate("100")
        confirm_path = r.headers["Location"]
        self.login(DONOR2, "donor")
        self.assertEqual(self.client.get(confirm_path).status_code, 404)

    def test_history_needs_donor_login(self):
        self.assertEqual(self.client.get("/donor/donations").status_code, 302)
        self.login("volunteer@example.com", "volunteer")
        self.assertEqual(self.client.get("/donor/donations").status_code, 302)

    # -- progress and dashboard --
    def test_progress_on_detail_and_cards(self):
        self.login()
        self.donate("250")
        public = create_app().test_client()
        detail = public.get(f"/campaigns/{self.cid}").get_data(as_text=True)
        self.assertIn("₹250", detail)
        self.assertIn("25%", detail)
        self.assertIn("width: 25%", public.get("/campaigns").get_data(as_text=True))

    def test_progress_reaches_100_at_goal(self):
        self.login()
        self.assertEqual(self.donate("1000").status_code, 302)      # goal is 1000
        detail = create_app().test_client().get(f"/campaigns/{self.cid}").get_data(as_text=True)
        self.assertIn("width: 100%", detail)
        self.assertIn("Goal reached", detail)
        self.assertNotIn("Donate Now", detail)

    def test_donation_above_goal_is_rejected(self):
        self.login()
        r = self.donate("5000")                                      # goal is 1000
        self.assertEqual(r.status_code, 400)
        page = r.get_data(as_text=True)
        self.assertIn("Payment rejected", page)
        self.assertIn("₹1,000 or less", page)
        self.assertEqual(self.count(), 0)

    def test_only_the_remaining_amount_is_accepted(self):
        self.login()
        self.assertEqual(self.donate("700").status_code, 302)
        r = self.donate("400")                                       # only 300 still needed
        self.assertEqual(r.status_code, 400)
        self.assertIn("₹300 or less", r.get_data(as_text=True))
        self.assertEqual(self.count(), 1)
        self.assertEqual(self.donate("300").status_code, 302)        # exactly the rest is fine
        self.assertEqual(float(sql("SELECT SUM(amount) s FROM donations WHERE campaign_id=%s", (self.cid,))[0]["s"]), 1000.0)

    def test_full_campaign_accepts_no_more(self):
        self.login()
        self.donate("1000")
        for method in ("get", "post"):
            if method == "get":
                r = self.client.get(f"/campaigns/{self.cid}/donate")
            else:
                r = self.client.post(f"/campaigns/{self.cid}/donate",
                                     data={"amount": "1", "csrf_token": self.token("/campaigns")})
            self.assertEqual(r.status_code, 302)
        self.assertEqual(self.count(), 1)

    def test_donate_page_shows_amount_still_needed(self):
        self.login()
        self.donate("250")
        page = self.client.get(f"/campaigns/{self.cid}/donate").get_data(as_text=True)
        self.assertIn("Still needed", page)
        self.assertIn("₹750", page)

    def test_two_donors_at_once_cannot_pass_the_goal(self):
        import threading
        results = []
        def worker(email):
            c = create_app().test_client()
            tok = re.search(r'name="csrf_token" value="([^"]+)"', c.get("/login").get_data(as_text=True)).group(1)
            c.post("/login", data={"email": email, "password": PASSWORD, "role": "donor", "csrf_token": tok})
            tok = re.search(r'name="csrf_token" value="([^"]+)"',
                            c.get(f"/campaigns/{self.cid}/donate").get_data(as_text=True)).group(1)
            results.append(c.post(f"/campaigns/{self.cid}/donate", data={"amount": "800", "csrf_token": tok}).status_code)
        ts = [threading.Thread(target=worker, args=(e,)) for e in ("donor@example.com", DONOR2)]
        [t.start() for t in ts]; [t.join() for t in ts]
        self.assertEqual(sorted(results), [302, 400])
        self.assertEqual(self.count(), 1)

    def test_donate_button_visibility(self):
        public = create_app().test_client().get(f"/campaigns/{self.cid}").get_data(as_text=True)
        self.assertIn("Donate Now", public)
        self.login("volunteer@example.com", "volunteer")
        page = self.client.get(f"/campaigns/{self.cid}").get_data(as_text=True)
        self.assertNotIn("Donate Now", page)
        self.assertIn("Only donors can make donations", page)

    def test_donor_dashboard_shows_real_totals(self):
        self.login(DONOR2, "donor")
        self.donate("400")
        page = self.client.get("/donor").get_data(as_text=True)
        self.assertIn("₹400", page)
        self.assertIn("Recent Donations", page)
        self.assertIn(TITLE, page)

    def test_home_counts_donations(self):
        self.login()
        self.donate("100")
        n = sql("SELECT COUNT(*) AS n FROM donations")[0]["n"]
        page = create_app().test_client().get("/").get_data(as_text=True)
        self.assertRegex(page, r"<strong>%d</strong><span>Test Donations Made" % n)

    def test_text_in_campaign_title_is_escaped_on_donate_page(self):
        sql("UPDATE campaigns SET title=%s WHERE campaign_id=%s", ("TEST Donation Drive <b>x</b>", self.cid))
        try:
            self.login()
            page = self.client.get(f"/campaigns/{self.cid}/donate").get_data(as_text=True)
            self.assertNotIn("<b>x</b>", page)
        finally:
            sql("UPDATE campaigns SET title=%s WHERE campaign_id=%s", (TITLE, self.cid))


if __name__ == "__main__":
    unittest.main()
