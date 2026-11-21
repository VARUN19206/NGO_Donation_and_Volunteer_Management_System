"""Module 4 tests: volunteer tasks, PDF receipt, photo updates, emails, donation tracker.

Run on a test database:  DB_NAME=ngo_donation_test python -m unittest discover -s tests -v
"""
import io
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import _env  # noqa: F401,E402  (must be first: temp upload/outbox folders)

from PIL import Image  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402

import config  # noqa: E402
import db  # noqa: E402
from app import create_app  # noqa: E402

PASSWORD = "Demo@1234"
TITLE = "TEST Module4 Campaign"
OTHER_ADMIN = "other.admin@t.example"
VOL2 = "vol2@t.example"
DONOR2 = "donor2m4@t.example"


def sql(statement, params=()):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(statement, params)
            return cur.fetchall()
    finally:
        conn.close()


def photo(fmt="JPEG", size=(300, 200), name="p.jpg"):
    buf = io.BytesIO()
    Image.new("RGB", size, (30, 120, 200)).save(buf, fmt)
    buf.seek(0)
    return (buf, name)


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if "test" not in os.environ["DB_NAME"]:
            raise RuntimeError("Tests must run on a database whose name contains 'test'.")

    def setUp(self):
        self.cleanup()
        self.owner = sql("SELECT user_id FROM users WHERE email='campaign.admin@example.com'")[0]["user_id"]
        sql("INSERT INTO campaigns (title, description, category, goal_amount, created_by) VALUES (%s,%s,%s,%s,%s)",
            (TITLE, "A test campaign used only by the automated tests of Module 4.", "food", 1000, self.owner))
        self.cid = sql("SELECT campaign_id FROM campaigns WHERE title=%s", (TITLE,))[0]["campaign_id"]
        h = generate_password_hash(PASSWORD, method="pbkdf2:sha256")
        for name, email, role in (("Other Admin", OTHER_ADMIN, "campaign_admin"),
                                  ("Second Volunteer", VOL2, "volunteer"),
                                  ("Second Donor", DONOR2, "donor")):
            sql("INSERT INTO users (full_name, email, password_hash, role) VALUES (%s,%s,%s,%s)", (name, email, h, role))
        self.vol = sql("SELECT user_id FROM users WHERE email='volunteer@example.com'")[0]["user_id"]
        self.vol2 = sql("SELECT user_id FROM users WHERE email=%s", (VOL2,))[0]["user_id"]
        self.client = create_app().test_client()

    def tearDown(self):
        self.cleanup()

    def cleanup(self):
        cid = "(SELECT campaign_id FROM (SELECT campaign_id FROM campaigns WHERE title=%s) x)"
        sql(f"DELETE FROM email_log WHERE update_id IN (SELECT update_id FROM campaign_updates WHERE campaign_id IN {cid})", (TITLE,))
        sql(f"DELETE FROM update_images WHERE update_id IN (SELECT update_id FROM campaign_updates WHERE campaign_id IN {cid})", (TITLE,))
        sql(f"DELETE FROM campaign_updates WHERE campaign_id IN {cid}", (TITLE,))
        sql(f"DELETE FROM tasks WHERE campaign_id IN {cid}", (TITLE,))
        sql(f"DELETE FROM donations WHERE campaign_id IN {cid}", (TITLE,))
        sql("DELETE FROM campaigns WHERE title=%s", (TITLE,))
        sql("DELETE FROM users WHERE email IN (%s,%s,%s)", (OTHER_ADMIN, VOL2, DONOR2))

    def token(self, path="/login"):
        for page in (path, "/dashboard"):          # fall back to the logout form on the dashboard
            html = self.client.get(page, follow_redirects=True).get_data(as_text=True)
            found = re.search(r'name="csrf_token" value="([^"]+)"', html)
            if found:
                return found.group(1)
        raise AssertionError("no CSRF token found")

    def login(self, email, tab):
        self.client = create_app().test_client()
        return self.client.post("/login", data={"email": email, "password": PASSWORD, "role": tab,
                                                "csrf_token": self.token("/login")})

    def as_donor(self, email="donor@example.com"):
        self.login(email, "donor")

    def as_admin(self, email="campaign.admin@example.com"):
        self.login(email, "admin")

    def as_volunteer(self, email="volunteer@example.com"):
        self.login(email, "volunteer")

    def donate(self, amount="500"):
        self.client.post(f"/campaigns/{self.cid}/donate",
                         data={"amount": amount, "csrf_token": self.token(f"/campaigns/{self.cid}/donate")})
        return sql("SELECT donation_id FROM donations WHERE campaign_id=%s ORDER BY donation_id DESC", (self.cid,))[0]["donation_id"]

    def post_update(self, files=None, cid=None, **fields):
        cid = cid or self.cid
        path = f"/manage/campaigns/{cid}/updates/new"
        data = {"title": "Food packets delivered", "description": "We delivered food packets to families this week.",
                "amount_used": "400", "csrf_token": self.token(path)}
        data.update(fields)
        data["photos"] = files if files is not None else [photo()]
        return self.client.post(path, data=data, content_type="multipart/form-data")

    def outbox(self):
        d = config.OUTBOX_DIR
        return sorted(d.glob("*.eml")) if d.exists() else []


class TaskTests(Base):
    def new_task(self, **over):
        data = {"title": "Pack food", "description": "Pack and hand out food packets.", "campaign_id": str(self.cid),
                "assigned_to": str(self.vol), "due_date": "", "csrf_token": self.token("/manage/tasks/new")}
        data.update(over)
        return self.client.post("/manage/tasks/new", data=data)

    def task_id(self):
        return sql("SELECT task_id FROM tasks WHERE campaign_id=%s", (self.cid,))[0]["task_id"]

    def test_admin_creates_task_and_volunteer_sees_it(self):
        self.as_admin()
        self.assertEqual(self.new_task().status_code, 302)
        self.as_volunteer()
        self.assertIn("Pack food", self.client.get("/volunteer/tasks").get_data(as_text=True))

    def test_volunteer_does_not_see_others_tasks(self):
        self.as_admin()
        self.new_task(assigned_to=str(self.vol2))
        self.as_volunteer()
        self.assertNotIn("Pack food", self.client.get("/volunteer/tasks").get_data(as_text=True))

    def test_task_validation(self):
        self.as_admin()
        for bad in ({"title": "ab"}, {"description": "short"}, {"assigned_to": "999999"},
                    {"campaign_id": "999999"}, {"due_date": "2001-01-01"}, {"due_date": "nonsense"}):
            self.assertEqual(self.new_task(**bad).status_code, 400, bad)
        self.assertEqual(sql("SELECT COUNT(*) n FROM tasks WHERE campaign_id=%s", (self.cid,))[0]["n"], 0)

    def test_cannot_assign_task_to_a_donor(self):
        self.as_admin()
        donor = sql("SELECT user_id FROM users WHERE email='donor@example.com'")[0]["user_id"]
        self.assertEqual(self.new_task(assigned_to=str(donor)).status_code, 400)

    def test_other_admin_cannot_use_my_campaign(self):
        self.as_admin(OTHER_ADMIN)
        self.assertEqual(self.new_task().status_code, 400)

    def test_other_admin_cannot_edit_task(self):
        self.as_admin()
        self.new_task()
        tid = self.task_id()
        self.as_admin(OTHER_ADMIN)
        r = self.client.get(f"/manage/tasks/{tid}/edit")
        self.assertEqual(r.status_code, 302)
        self.assertNotIn("Pack food", self.client.get("/manage/tasks").get_data(as_text=True))

    def test_platform_admin_can_edit(self):
        self.as_admin()
        self.new_task()
        tid = self.task_id()
        self.as_admin("platform.admin@example.com")
        self.assertEqual(self.client.get(f"/manage/tasks/{tid}/edit").status_code, 200)

    def test_volunteer_updates_own_status_only(self):
        self.as_admin()
        self.new_task()
        tid = self.task_id()
        self.as_volunteer()
        r = self.client.post(f"/volunteer/tasks/{tid}/status",
                             data={"status": "in_progress", "csrf_token": self.token("/volunteer/tasks")})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(sql("SELECT status FROM tasks WHERE task_id=%s", (tid,))[0]["status"], "in_progress")
        self.client.post(f"/volunteer/tasks/{tid}/status",
                         data={"status": "bogus", "csrf_token": self.token("/volunteer/tasks")})
        self.assertEqual(sql("SELECT status FROM tasks WHERE task_id=%s", (tid,))[0]["status"], "in_progress")
        self.as_volunteer(VOL2)
        r = self.client.post(f"/volunteer/tasks/{tid}/status",
                             data={"status": "completed", "csrf_token": self.token("/volunteer/tasks")})
        self.assertEqual(r.status_code, 404)
        self.assertEqual(sql("SELECT status FROM tasks WHERE task_id=%s", (tid,))[0]["status"], "in_progress")

    def test_role_gates(self):
        self.as_donor()
        self.assertNotEqual(self.client.get("/volunteer/tasks").status_code, 200)
        self.assertNotEqual(self.client.get("/manage/tasks").status_code, 200)
        self.as_volunteer()
        self.assertNotEqual(self.client.get("/manage/tasks/new").status_code, 200)

    def test_volunteer_dashboard_counts(self):
        self.as_admin()
        self.new_task()
        self.as_volunteer()
        html = self.client.get("/volunteer").get_data(as_text=True)
        self.assertIn("Tasks Assigned", html)
        self.assertIn("Pack food", html)


class ReceiptTests(Base):
    def test_donor_downloads_own_receipt(self):
        self.as_donor()
        did = self.donate("2500")
        r = self.client.get(f"/donations/{did}/receipt")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.mimetype, "application/pdf")
        self.assertIn("attachment", r.headers["Content-Disposition"])
        pdf = r.get_data()
        self.assertTrue(pdf.startswith(b"%PDF"))
        ref = sql("SELECT transaction_ref FROM donations WHERE donation_id=%s", (did,))[0]["transaction_ref"]
        self.assertIn(ref.encode(), pdf)
        self.assertIn(b"Rs. 2,500.00", pdf)
        self.assertIn(b"SIMULATED TEST TRANSACTION", pdf)

    def test_confirmation_page_has_download_button(self):
        self.as_donor()
        did = self.donate()
        html = self.client.get(f"/donations/{did}").get_data(as_text=True)
        self.assertIn(f"/donations/{did}/receipt", html)

    def test_cannot_download_someone_elses_receipt(self):
        self.as_donor()
        did = self.donate()
        self.as_donor(DONOR2)
        self.assertEqual(self.client.get(f"/donations/{did}/receipt").status_code, 404)

    def test_logged_out_and_non_donor_blocked(self):
        self.as_donor()
        did = self.donate()
        self.client = create_app().test_client()
        self.assertEqual(self.client.get(f"/donations/{did}/receipt").status_code, 302)
        self.as_volunteer()
        self.assertNotEqual(self.client.get(f"/donations/{did}/receipt").status_code, 200)


class UpdateTests(Base):
    def test_admin_posts_update_with_photo(self):
        self.as_admin()
        r = self.post_update()
        self.assertEqual(r.status_code, 302)
        row = sql("SELECT u.update_id, i.filename FROM campaign_updates u JOIN update_images i USING(update_id) "
                  "WHERE u.campaign_id=%s", (self.cid,))
        self.assertEqual(len(row), 1)
        self.assertTrue((config.UPLOAD_DIR / row[0]["filename"]).exists())
        self.assertRegex(row[0]["filename"], r"^[0-9a-f]{32}\.jpg$")
        # public can see the update and the picture
        self.client = create_app().test_client()
        html = self.client.get(f"/campaigns/{self.cid}").get_data(as_text=True)
        self.assertIn("Food packets delivered", html)
        img = self.client.get(f"/uploads/{row[0]['filename']}")
        self.assertEqual(img.status_code, 200)
        self.assertEqual(img.mimetype, "image/jpeg")

    def test_photo_required_and_limits(self):
        self.as_admin()
        self.assertEqual(self.post_update(files=[]).status_code, 400)
        five = [photo(name=f"{i}.jpg") for i in range(5)]
        self.assertEqual(self.post_update(files=five).status_code, 400)
        self.assertEqual(sql("SELECT COUNT(*) n FROM campaign_updates WHERE campaign_id=%s", (self.cid,))[0]["n"], 0)

    def test_fake_image_rejected(self):
        self.as_admin()
        fake = (io.BytesIO(b"<?php echo 1; ?>"), "shell.jpg")
        self.assertEqual(self.post_update(files=[fake]).status_code, 400)
        gif = io.BytesIO()
        Image.new("RGB", (10, 10)).save(gif, "GIF")
        gif.seek(0)
        self.assertEqual(self.post_update(files=[(gif, "a.gif")]).status_code, 400)

    def test_png_converted_and_large_resized_and_exif_stripped(self):
        self.as_admin()
        buf = io.BytesIO()
        img = Image.new("RGB", (3000, 2000), (10, 200, 10))
        exif = Image.Exif()
        exif[0x010F] = "SecretCamera"
        img.save(buf, "JPEG", exif=exif)
        buf.seek(0)
        self.assertEqual(self.post_update(files=[(buf, "big.jpg"), photo("PNG", name="x.png")]).status_code, 302)
        names = [r["filename"] for r in sql("SELECT filename FROM update_images")]
        mine = [n for n in names if (config.UPLOAD_DIR / n).exists()]
        sizes = []
        for n in mine:
            with Image.open(config.UPLOAD_DIR / n) as im:
                self.assertEqual(im.format, "JPEG")
                self.assertEqual(len(im.getexif()), 0)
                sizes.append(max(im.size))
        self.assertTrue(all(s <= 1600 for s in sizes))

    def test_validation_errors(self):
        self.as_admin()
        for bad in ({"title": "ab"}, {"description": "too short"}, {"amount_used": "abc"},
                    {"amount_used": "-5"}, {"amount_used": "1.234"}):
            self.assertEqual(self.post_update(**bad).status_code, 400, bad)

    def test_only_owner_or_platform_admin_may_post(self):
        self.as_admin(OTHER_ADMIN)
        self.post_update()
        self.assertEqual(sql("SELECT COUNT(*) n FROM campaign_updates WHERE campaign_id=%s", (self.cid,))[0]["n"], 0)
        self.as_donor()
        self.assertNotEqual(self.client.get(f"/manage/campaigns/{self.cid}/updates/new").status_code, 200)
        self.as_admin("platform.admin@example.com")
        self.assertEqual(self.post_update().status_code, 302)

    def test_upload_route_is_restricted(self):
        for bad in ("../app.py", "abc.jpg", "x.png", "%2e%2e%2fapp.py", "A" * 32 + ".jpg"):
            self.assertEqual(self.client.get(f"/uploads/{bad}").status_code, 404, bad)

    def test_csrf_required_for_update(self):
        self.as_admin()
        r = self.client.post(f"/manage/campaigns/{self.cid}/updates/new",
                             data={"title": "x", "photos": photo()}, content_type="multipart/form-data")
        self.assertEqual(r.status_code, 400)

    def test_html_is_escaped(self):
        self.as_admin()
        self.post_update(title="<script>alert(1)</script> done")
        html = self.client.get(f"/campaigns/{self.cid}").get_data(as_text=True)
        self.assertNotIn("<script>alert(1)</script>", html)


class EmailAndTrackerTests(Base):
    def setUp(self):
        super().setUp()
        for f in self.outbox():
            f.unlink()

    def test_each_donor_gets_one_email_with_photo(self):
        self.as_donor()
        self.donate()
        self.donate("200")                       # same donor twice -> still one email
        self.as_donor(DONOR2)
        self.donate()
        self.as_admin()
        self.post_update()
        files = self.outbox()
        self.assertEqual(len(files), 2)
        text = files[0].read_bytes().decode("utf8", "ignore")
        self.assertIn("Food packets delivered", text)
        self.assertIn("Content-ID", text)
        self.assertIn("image/jpeg", text)
        log = sql("SELECT status FROM email_log")
        self.assertEqual([r["status"] for r in log if r["status"] == "saved"], ["saved", "saved"])

    def test_only_donors_of_that_campaign_are_emailed(self):
        self.as_donor()                          # donor@example.com has not donated here
        self.as_admin()
        self.post_update()
        self.assertEqual(len(self.outbox()), 0)

    def test_deactivated_donor_not_emailed(self):
        self.as_donor(DONOR2)
        self.donate()
        sql("UPDATE users SET is_active=0 WHERE email=%s", (DONOR2,))
        self.as_admin()
        self.post_update()
        self.assertEqual(len(self.outbox()), 0)

    def test_email_html_escapes_user_text(self):
        self.as_donor()
        self.donate()
        self.as_admin()
        self.post_update(title="Hi <b>bold</b>")
        text = self.outbox()[0].read_bytes().decode("utf8", "ignore")
        self.assertNotIn("<h2 style='color:#0f2a52'>Hi <b>", text)

    def test_tracker_shows_updates_after_donation(self):
        self.as_donor()
        self.donate()
        self.as_admin()
        self.post_update()
        self.as_donor()
        html = self.client.get("/donor/tracker").get_data(as_text=True)
        self.assertIn(TITLE, html)
        self.assertIn("Food packets delivered", html)
        self.assertIn("/uploads/", html)

    def test_tracker_hides_campaigns_not_donated_to(self):
        self.as_admin()
        self.post_update()
        self.as_donor(DONOR2)
        self.assertNotIn(TITLE, self.client.get("/donor/tracker").get_data(as_text=True))

    def test_tracker_is_donor_only(self):
        self.as_volunteer()
        self.assertNotEqual(self.client.get("/donor/tracker").status_code, 200)

    def test_smtp_failure_is_logged_and_does_not_break_post(self):
        self.as_donor()
        self.donate()
        old = config.SMTP_HOST, config.SMTP_PORT
        config.SMTP_HOST, config.SMTP_PORT = "127.0.0.1", 1      # nothing listens here
        try:
            self.as_admin()
            r = self.post_update()
        finally:
            config.SMTP_HOST, config.SMTP_PORT = old
        self.assertEqual(r.status_code, 302)
        self.assertEqual(sql("SELECT COUNT(*) n FROM campaign_updates WHERE campaign_id=%s", (self.cid,))[0]["n"], 1)
        self.assertEqual([x["status"] for x in sql("SELECT status FROM email_log")], ["failed"])

    def test_real_smtp_path(self):
        try:
            from aiosmtpd.controller import Controller
        except ImportError:
            self.skipTest("aiosmtpd not installed")
        got = []

        class Handler:
            async def handle_DATA(self, server, session, envelope):
                got.append(envelope.content)
                return "250 OK"

        ctl = Controller(Handler(), hostname="127.0.0.1", port=8026)
        ctl.start()
        old = (config.SMTP_HOST, config.SMTP_PORT, config.SMTP_TLS)
        config.SMTP_HOST, config.SMTP_PORT, config.SMTP_TLS = "127.0.0.1", 8026, False
        try:
            self.as_donor()
            self.donate()
            self.as_admin()
            self.post_update()
        finally:
            config.SMTP_HOST, config.SMTP_PORT, config.SMTP_TLS = old
            ctl.stop()
        self.assertEqual(len(got), 1)
        self.assertIn(b"Food packets delivered", got[0])
        self.assertEqual([x["status"] for x in sql("SELECT status FROM email_log")], ["sent"])


if __name__ == "__main__":
    unittest.main()
