"""Module 2: home page, campaign list and details, and campaign management for admins."""
import re
from decimal import Decimal

from flask import (Blueprint, abort, flash, redirect, render_template, request,
                   url_for)

import config
import db
from auth import current_user, role_required

bp = Blueprint("campaigns", __name__)

ADMIN_ROLES = ("campaign_admin", "platform_admin")
GOAL_RE = re.compile(r"^\d{1,9}(\.\d{1,2})?$")
MAX_GOAL = Decimal("100000000")          # 10 crore


def inr(value):
    """Format a number as Indian rupees, e.g. 150000 -> ₹1,50,000."""
    d = Decimal(value)
    whole = str(int(d))
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        whole = ",".join(parts + [tail])
    paise = int((d - int(d)) * 100)
    return "₹" + whole + (f".{paise:02d}" if paise else "")


# ---------- helpers ----------

CAMPAIGN_SELECT = (
    "SELECT c.campaign_id, c.title, c.description, c.category, c.goal_amount, "
    "c.status, c.created_by, c.created_at, u.full_name AS organiser "
    "FROM campaigns c JOIN users u ON u.user_id = c.created_by ")


def get_campaign(campaign_id):
    return db.query_one(CAMPAIGN_SELECT + "WHERE c.campaign_id = %s", (campaign_id,))


def can_edit(user, campaign):
    if not user:
        return False
    if user["role"] == "platform_admin":
        return True
    return user["role"] == "campaign_admin" and campaign["created_by"] == user["user_id"]


def validate_campaign(form, editing):
    title = " ".join(form.get("title", "").split())
    description = form.get("description", "").replace("\r\n", "\n").strip()
    category = form.get("category", "")
    goal_text = form.get("goal_amount", "").replace(",", "").strip()
    status = form.get("status", "active") if editing else "active"
    errors = []

    if not 3 <= len(title) <= 120:
        errors.append("Title must be 3 to 120 characters.")
    if not 20 <= len(description) <= 2000:
        errors.append("Description must be 20 to 2000 characters.")
    if category not in config.CATEGORIES:
        errors.append("Choose a category.")
    goal = None
    if not GOAL_RE.match(goal_text) or not (Decimal("1") <= Decimal(goal_text) <= MAX_GOAL):
        errors.append("Goal amount must be a number from 1 to 10,00,00,000 (up to 2 decimals).")
    else:
        goal = Decimal(goal_text)
    if status not in config.CAMPAIGN_STATUSES:
        errors.append("Choose a valid status.")

    values = {"title": title, "description": description, "category": category,
              "goal_amount": goal_text, "status": status}
    return values, goal, errors


# ---------- public pages ----------

@bp.route("/")
def home():
    featured = db.all_rows(CAMPAIGN_SELECT +
                           "WHERE c.status = 'active' ORDER BY c.created_at DESC, c.campaign_id DESC LIMIT 3")
    stats = {
        "campaigns": db.query_one("SELECT COUNT(*) AS n FROM campaigns WHERE status = 'active'")["n"],
        "donors": db.query_one("SELECT COUNT(*) AS n FROM users WHERE role = 'donor' AND is_active = 1")["n"],
        "volunteers": db.query_one("SELECT COUNT(*) AS n FROM users WHERE role = 'volunteer' AND is_active = 1")["n"],
    }
    return render_template("home.html", featured=featured, stats=stats, active_nav="home")


@bp.route("/campaigns")
def listing():
    rows = db.all_rows(CAMPAIGN_SELECT +
                       "WHERE c.status = 'active' ORDER BY c.created_at DESC, c.campaign_id DESC")
    return render_template("campaigns.html", campaigns=rows, active_nav="campaigns")


@bp.route("/campaigns/<int:campaign_id>")
def detail(campaign_id):
    campaign = get_campaign(campaign_id)
    if campaign is None:
        abort(404)
    return render_template("campaign_detail.html", c=campaign,
                           can_edit=can_edit(current_user(), campaign),
                           active_nav="campaigns")


# ---------- management (campaign admin / platform admin) ----------

@bp.route("/manage/campaigns")
@role_required(*ADMIN_ROLES)
def manage(user):
    if user["role"] == "platform_admin":
        rows = db.all_rows(CAMPAIGN_SELECT + "ORDER BY c.created_at DESC, c.campaign_id DESC")
    else:
        rows = db.all_rows(CAMPAIGN_SELECT + "WHERE c.created_by = %s "
                           "ORDER BY c.created_at DESC, c.campaign_id DESC", (user["user_id"],))
    return render_template("manage_campaigns.html", user=user, campaigns=rows,
                           active_nav="campaigns")


@bp.route("/manage/campaigns/new", methods=["GET", "POST"])
@role_required(*ADMIN_ROLES)
def create(user):
    if request.method == "POST":
        values, goal, errors = validate_campaign(request.form, editing=False)
        if not errors:
            db.execute(
                "INSERT INTO campaigns (title, description, category, goal_amount, created_by) "
                "VALUES (%s, %s, %s, %s, %s)",
                (values["title"], values["description"], values["category"], goal, user["user_id"]))
            flash("Campaign created.", "success")
            return redirect(url_for("campaigns.manage"))
        for e in errors:
            flash(e, "error")
        return render_template("campaign_form.html", user=user, form=values, editing=False,
                               active_nav="campaigns"), 400
    return render_template("campaign_form.html", user=user, editing=False, active_nav="campaigns",
                           form={"category": "education", "status": "active"})


@bp.route("/manage/campaigns/<int:campaign_id>/edit", methods=["GET", "POST"])
@role_required(*ADMIN_ROLES)
def edit(user, campaign_id):
    campaign = get_campaign(campaign_id)
    if campaign is None:
        abort(404)
    if not can_edit(user, campaign):
        flash("You can only edit campaigns that you created.", "error")
        return redirect(url_for("campaigns.manage"))

    if request.method == "POST":
        values, goal, errors = validate_campaign(request.form, editing=True)
        if not errors:
            db.execute(
                "UPDATE campaigns SET title = %s, description = %s, category = %s, "
                "goal_amount = %s, status = %s WHERE campaign_id = %s",
                (values["title"], values["description"], values["category"], goal,
                 values["status"], campaign_id))
            flash("Campaign updated.", "success")
            return redirect(url_for("campaigns.manage"))
        for e in errors:
            flash(e, "error")
        return render_template("campaign_form.html", user=user, form=values, editing=True,
                               campaign=campaign, active_nav="campaigns"), 400

    form = {"title": campaign["title"], "description": campaign["description"],
            "category": campaign["category"], "status": campaign["status"],
            "goal_amount": str(campaign["goal_amount"]).rstrip("0").rstrip(".")}
    return render_template("campaign_form.html", user=user, form=form, editing=True,
                           campaign=campaign, active_nav="campaigns")
