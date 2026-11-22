# NGO Donation and Volunteer Management System
## Modules 1 to 5 (all increments) + receipt, donation tracker and email updates

Python Flask + MySQL + HTML/CSS/JS, as in the approved synopsis.

| Module | What it does | Main files |
|---|---|---|
| **1. Database and User Authentication** | `users` table, Register, Login, password hashing, roles | `auth.py`, `templates/login.html`, `register.html` |
| **2. Campaign Management** | Home page, campaign list and details, create and edit campaign | `campaigns.py`, `templates/home.html`, `campaigns.html`, `campaign_detail.html`, `manage_campaigns.html`, `campaign_form.html` |
| **4. Volunteer Management** | Admin creates tasks and assigns them to a volunteer; volunteer sees My Tasks and updates status (To do, In progress, Completed) | `tasks.py`, `templates/volunteer_tasks.html`, `manage_tasks.html`, `task_form.html` |
| **5. Admin: Users, Records and Reports** | Platform admin activates/deactivates users; admins view donation records and campaign reports; CSV download | `admin.py`, `templates/admin_users.html`, `admin_donations.html`, `admin_reports.html` |
| **Extra A: Receipt** | Donor downloads a PDF receipt after a donation | `receipt.py` |
| **Extra B: Donation tracker + email** | Campaign admin posts an update with photo proof; donors of that campaign are emailed; donors follow updates on Donation Tracker | `updates.py`, `mailer.py`, `templates/update_form.html`, `tracker.html` |
| **3. Donation Management** | Select campaign, enter amount, save donation record, confirmation, donation history | `donations.py`, `templates/donate.html`, `donation_confirmation.html`, `donation_history.html` |


> **Donations are simulated test transactions.** No real payment gateway is used and no money is charged. Every donation gets a test reference such as `TEST-1A2B3C4D5E`. The screens say so clearly.

## Run it

```
pip install -r requirements.txt
copy .env.example .env          (Mac/Linux: cp .env.example .env)
```
Open `.env` and type your MySQL password after `DB_PASSWORD=`. Then:
```
python init_db.py
python app.py
```
Open **http://127.0.0.1:5000**

**Already ran Module 1 or 2?** Just run `python init_db.py` again. It adds the new tables and keeps your existing users and campaigns.

## Pages

| Page | Address | Who can open it |
|---|---|---|
| Home (hero, live counts, ongoing campaigns with progress) | `/` | Everyone |
| All campaigns | `/campaigns` | Everyone |
| Campaign details (description, raised amount, Donate button) | `/campaigns/<id>` | Everyone |
| Login / Register | `/login`, `/register` | Everyone |
| Donate (enter amount) | `/campaigns/<id>/donate` | Donors only (others are asked to log in or told only donors can donate) |
| Donation confirmation | `/donations/<id>` | The donor who made it |
| My Donations (history and total) | `/donor/donations` | Donors |
| Role dashboard | `/donor`, `/volunteer`, `/admin` | Matching role only |
| Manage Users | `/admin/users` | Platform Admin |
| Donation Records / Reports (+ CSV) | `/admin/donations`, `/admin/reports` | Campaign Admin (own campaigns), Platform Admin |
| Manage / Create / Edit campaign | `/manage/campaigns...` | Campaign Admin, Platform Admin |
| Download receipt | `/donations/<id>/receipt` | The donor who made it |
| Donation Tracker | `/donor/tracker` | Donors |
| Post update with photos | `/manage/campaigns/<id>/updates/new` | Owner Campaign Admin, Platform Admin |
| My Tasks / change status | `/volunteer/tasks` | Volunteers (own tasks only) |
| Manage Tasks / New / Edit | `/manage/tasks...` | Campaign Admin (own campaigns), Platform Admin |

## Module 5: admin tools
- **Manage Users** (platform admin only): list by role, **Deactivate / Activate**. A deactivated user cannot log in and an already logged-in session stops working at once. You cannot deactivate yourself or a platform admin. Accounts are never deleted, so donation records stay intact.
- **Donation Records:** every saved test donation with donor, campaign, amount and reference; filter by campaign; **Download CSV**.
- **Reports:** per campaign goal, raised, progress, donors, donations and tasks completed, with totals; **Download CSV**.
- **Who sees what:** the platform admin sees everything; a campaign admin sees only the records and reports of their own campaigns.
- CSV cells starting with `=`, `+`, `-` or `@` are saved as text so Excel never runs them as formulas.

## Receipt, tracker and emails
- **Receipt:** after a donation, **Download Receipt (PDF)** (also on My Donations). It is a **test receipt** and says so: no real payment, not valid for tax exemption. Amounts show as `Rs.` because the PDF font has no rupee sign.
- **Post update (admin):** Manage Campaigns, **Post update**. Title, description, optional amount used, 1 to 4 photos (JPG/PNG/WEBP, 8 MB each). Photos are checked, resized and re-saved as JPEG with location data removed. Campaign admins can post only for their own campaigns; the platform admin for any.
- **Public:** updates and photos appear on the campaign page under "Where the donations helped".
- **Donation Tracker (donor):** for every campaign the donor supported, the updates posted since their first donation. These are campaign-level updates, not a trace of one person's rupees.
- **Emails:** when an update is posted, each donor of that campaign (once, even if they donated many times) gets an email with the text and photos.
  - **No setup needed:** without SMTP settings the emails are saved as `.eml` files in the `outbox/` folder. Double-click one to read it.
  - **Real sending:** fill the `SMTP_*` lines in `.env` (see `.env.example`). For Gmail use `smtp.gmail.com`, port 587 and an **App password** (not your normal password).
  - Every email attempt is recorded in the `email_log` table (sent / saved / failed). A failed email never blocks posting the update.
- No sample updates or photos are added by `init_db.py`; the admin uploads real ones.

## Donor workflow (matches slide 9)
Browse Campaigns, select a campaign, **Donate Now**, Login or Register if needed (you come back to the donate page afterwards), enter the amount, **Donate (test)**, see the confirmation, view My Donations.

## Donation rules
- Only users with the **Donor** role can donate. Volunteers and admins cannot.
- Only **active** campaigns accept donations. Closed campaigns do not.
- Amount: at least ₹1, up to 2 decimals (commas allowed, for example `1,250.50`).
- **A donation can never go past the campaign goal.** If a campaign needs ₹80,000 more and a donor enters ₹1,00,000, the payment is rejected with the message "Payment rejected ... Please donate ₹80,000 or less". The donate page shows how much is still needed. When the goal is reached, the Donate button is replaced by "Goal reached".
- The raised amount and progress bar on every campaign are the sum of the saved test donations. Progress stops at 100%.
- A donor can only see their own donations and confirmations.
- Home page counts (campaigns, donors, volunteers, test donations) are live database counts. Nothing is made up. A fresh database starts with 0 donations.

## Demo data (added by `init_db.py`)
Password for all demo accounts: `Demo@1234`

| Login tab | Email | Role |
|---|---|---|
| Donor | donor@example.com | Donor |
| Volunteer | volunteer@example.com | Volunteer |
| Admin | campaign.admin@example.com | Campaign Admin |
| Admin | platform.admin@example.com | Platform Admin |

It also adds 3 sample campaigns (Education Support, Food Distribution, Medical Camp) and 2 sample tasks for the demo volunteer. The text is sample content for testing only. Run `python init_db.py --no-demo` to skip all demo data.

## Security (OWASP-style, as on your references slide)
- Passwords stored only as salted PBKDF2-SHA256 hashes. One generic error for every failed login.
- Role checked on the login tab and again on every protected page.
- CSRF token on every form; logout is a POST.
- The "come back after login" link only accepts pages on this site (no redirect to other websites).
- All database queries use parameters. All text shown on pages is escaped.

## Tests (105)
```
set DB_NAME=ngo_donation_test        (PowerShell: $env:DB_NAME="ngo_donation_test")
python init_db.py
python -m unittest discover -s tests -v
```
Tests use temporary upload and email folders and never touch your real ones. The real-SMTP test needs `pip install aiosmtpd` (skipped if missing). The tests refuse to run on a database whose name does not contain "test".

## Using a real photo on the home page
Put an image in `static/img/` and in `static/css/style.css` change `--hero-photo: none;` to
`--hero-photo: url("/static/img/hero.jpg");`

## Folder map
```
app.py          start the app, CSRF, error pages
auth.py         register, login, logout, role checks, dashboards, sidebar links
campaigns.py    home page, campaign list/details, create/edit
donations.py    donate (simulated), confirmation, history, receipt download
tasks.py        volunteer tasks (admin and volunteer sides)
updates.py      campaign updates with photos, donation tracker, donor emails
admin.py        user management, donation records, reports, CSV
receipt.py      PDF receipt          mailer.py   email sending / outbox
db.py           MySQL connection helpers
config.py       settings from .env, role and category names
init_db.py      creates database, tables, demo accounts and sample campaigns
schema.sql      users, campaigns, donations, tasks, campaign_updates, update_images, email_log
templates/      pages        static/   css and js        tests/   automated tests
```
