# NGO Donation and Volunteer Management System
## Modules 1, 2 and 3 (Increments 1 to 3)

Python Flask + MySQL + HTML/CSS/JS, as in the approved synopsis.

| Module | What it does | Main files |
|---|---|---|
| **1. Database and User Authentication** | `users` table, Register, Login, password hashing, roles | `auth.py`, `templates/login.html`, `register.html` |
| **2. Campaign Management** | Home page, campaign list and details, create and edit campaign | `campaigns.py`, `templates/home.html`, `campaigns.html`, `campaign_detail.html`, `manage_campaigns.html`, `campaign_form.html` |
| **3. Donation Management** | Select campaign, enter amount, save donation record, confirmation, donation history | `donations.py`, `templates/donate.html`, `donation_confirmation.html`, `donation_history.html` |

Volunteer tasks, reports and user management are **not** included (Modules 4 and 5).

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
| Manage / Create / Edit campaign | `/manage/campaigns...` | Campaign Admin, Platform Admin |

## Donor workflow (matches slide 9)
Browse Campaigns, select a campaign, **Donate Now**, Login or Register if needed (you come back to the donate page afterwards), enter the amount, **Donate (test)**, see the confirmation, view My Donations.

## Donation rules
- Only users with the **Donor** role can donate. Volunteers and admins cannot.
- Only **active** campaigns accept donations. Closed campaigns do not.
- Amount: ₹1 to ₹1,00,00,000, up to 2 decimals (commas allowed, for example `1,250.50`).
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

It also adds 3 sample campaigns (Education Support, Food Distribution, Medical Camp). The text is sample content for testing only. Run `python init_db.py --no-demo` to skip all demo data.

## Security (OWASP-style, as on your references slide)
- Passwords stored only as salted PBKDF2-SHA256 hashes. One generic error for every failed login.
- Role checked on the login tab and again on every protected page.
- CSRF token on every form; logout is a POST.
- The "come back after login" link only accepts pages on this site (no redirect to other websites).
- All database queries use parameters. All text shown on pages is escaped.

## Tests (54)
```
set DB_NAME=ngo_donation_test        (PowerShell: $env:DB_NAME="ngo_donation_test")
python init_db.py
python -m unittest discover -s tests -v
```
The tests refuse to run on a database whose name does not contain "test".

## Using a real photo on the home page
Put an image in `static/img/` and in `static/css/style.css` change `--hero-photo: none;` to
`--hero-photo: url("/static/img/hero.jpg");`

## Folder map
```
app.py          start the app, CSRF, error pages
auth.py         register, login, logout, role checks, dashboards, sidebar links
campaigns.py    home page, campaign list/details, create/edit
donations.py    donate (simulated), confirmation, history
db.py           MySQL connection helpers
config.py       settings from .env, role and category names
init_db.py      creates database, tables, demo accounts and sample campaigns
schema.sql      users, campaigns and donations tables
templates/      pages        static/   css and js        tests/   automated tests
```
