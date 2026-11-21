"""Module 5: admin tools - user management, donation records and reports.

Platform admin: all users, all campaigns. Campaign admin: only the records of their own campaigns.
"""
import csv
import io
from decimal import Decimal

from flask import (Blueprint, Response, abort, flash, redirect, render_template, request,
                   url_for)

import config
import db
from auth import role_required

bp = Blueprint("admin", __name__)
ADMIN_ROLES = ("campaign_admin", "platform_admin")


def scope(user, alias="c"):
    """SQL fragment and params limiting campaigns to what this admin may see."""
    if user["role"] == "platform_admin":
        return "1 = 1", ()
    return f"{alias}.created_by = %s", (user["user_id"],)


def csv_safe(value):
    """Stop spreadsheet formula injection: a cell starting with = + - @ is treated as text."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


# ---------- user management (platform admin) ----------

@bp.route("/admin/users")
@role_required("platform_admin")
def users(user):
    role = request.args.get("role", "")
    sql = ("SELECT user_id, full_name, email, role, is_active, created_at FROM users ")
    args = ()
    if role in config.ROLE_LABELS:
        sql += "WHERE role = %s "
        args = (role,)
    rows = db.all_rows(sql + "ORDER BY created_at DESC, user_id DESC", args)
    return render_template("admin_users.html", user=user, rows=rows, role=role,
                           active_nav="users")


@bp.route("/admin/users/<int:user_id>/active", methods=["POST"])
@role_required("platform_admin")
def set_active(user, user_id):
    target = db.query_one("SELECT user_id, full_name, role, is_active FROM users WHERE user_id = %s", (user_id,))
    if target is None:
        abort(404)
    make_active = request.form.get("active") == "1"
    if target["user_id"] == user["user_id"]:
        flash("You cannot deactivate your own account.", "error")
    elif not make_active and target["role"] == "platform_admin":
        flash("Platform admin accounts cannot be deactivated here.", "error")
    else:
        db.execute("UPDATE users SET is_active = %s WHERE user_id = %s", (1 if make_active else 0, user_id))
        flash(f"{target['full_name']} is now {'active' if make_active else 'deactivated'}.", "success")
    return redirect(request.referrer if False else url_for("admin.users", role=request.form.get("role", "")))


# ---------- donation records ----------

def donation_rows(user, campaign_id=None):
    where, args = scope(user)
    sql = ("SELECT d.donation_id, d.amount, d.transaction_ref, d.created_at, c.campaign_id, c.title, "
           "u.full_name AS donor_name, u.email AS donor_email "
           "FROM donations d JOIN campaigns c ON c.campaign_id = d.campaign_id "
           "JOIN users u ON u.user_id = d.donor_id WHERE " + where)
    args = list(args)
    if campaign_id:
        sql += " AND c.campaign_id = %s"
        args.append(campaign_id)
    return db.all_rows(sql + " ORDER BY d.created_at DESC, d.donation_id DESC", args)


def campaign_choices(user):
    where, args = scope(user)
    return db.all_rows(f"SELECT c.campaign_id, c.title FROM campaigns c WHERE {where} ORDER BY c.title", args)


@bp.route("/admin/donations")
@role_required(*ADMIN_ROLES)
def donations(user):
    choices = campaign_choices(user)
    try:
        cid = int(request.args.get("campaign", "")) if request.args.get("campaign") else None
    except ValueError:
        cid = None
    if cid and cid not in {c["campaign_id"] for c in choices}:
        cid = None
    rows = donation_rows(user, cid)
    total = sum((r["amount"] for r in rows), Decimal("0"))
    return render_template("admin_donations.html", user=user, rows=rows, total=total, choices=choices,
                           selected=cid, active_nav="donations")


@bp.route("/admin/donations.csv")
@role_required(*ADMIN_ROLES)
def donations_csv(user):
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["Date", "Campaign", "Donor", "Donor email", "Amount (INR)", "Test reference"])
    for r in donation_rows(user):
        w.writerow([r["created_at"].strftime("%Y-%m-%d %H:%M"), csv_safe(r["title"]), csv_safe(r["donor_name"]),
                    csv_safe(r["donor_email"]), f"{r['amount']:.2f}", r["transaction_ref"]])
    return Response(out.getvalue(), mimetype="text/csv", headers={
        "Content-Disposition": 'attachment; filename="donations-report.csv"'})


# ---------- reports ----------

@bp.route("/admin/reports")
@role_required(*ADMIN_ROLES)
def reports(user):
    where, args = scope(user)
    rows = db.all_rows(
        "SELECT c.campaign_id, c.title, c.status, c.goal_amount, "
        "COALESCE((SELECT SUM(amount) FROM donations d WHERE d.campaign_id = c.campaign_id), 0) AS raised, "
        "(SELECT COUNT(*) FROM donations d WHERE d.campaign_id = c.campaign_id) AS donations, "
        "(SELECT COUNT(DISTINCT donor_id) FROM donations d WHERE d.campaign_id = c.campaign_id) AS donors, "
        "(SELECT COUNT(*) FROM tasks t WHERE t.campaign_id = c.campaign_id) AS tasks, "
        "(SELECT COUNT(*) FROM tasks t WHERE t.campaign_id = c.campaign_id AND t.status = 'completed') AS tasks_done "
        f"FROM campaigns c WHERE {where} ORDER BY c.created_at DESC, c.campaign_id DESC", args)
    totals = {"raised": sum((r["raised"] for r in rows), Decimal("0")),
              "donations": sum(r["donations"] for r in rows),
              "tasks": sum(r["tasks"] for r in rows),
              "tasks_done": sum(int(r["tasks_done"]) for r in rows)}
    return render_template("admin_reports.html", user=user, rows=rows, totals=totals, active_nav="reports")


@bp.route("/admin/reports.csv")
@role_required(*ADMIN_ROLES)
def reports_csv(user):
    where, args = scope(user)
    rows = db.all_rows(
        "SELECT c.title, c.status, c.goal_amount, "
        "COALESCE((SELECT SUM(amount) FROM donations d WHERE d.campaign_id = c.campaign_id), 0) AS raised, "
        "(SELECT COUNT(*) FROM donations d WHERE d.campaign_id = c.campaign_id) AS donations, "
        "(SELECT COUNT(*) FROM tasks t WHERE t.campaign_id = c.campaign_id) AS tasks, "
        "(SELECT COUNT(*) FROM tasks t WHERE t.campaign_id = c.campaign_id AND t.status = 'completed') AS tasks_done "
        f"FROM campaigns c WHERE {where} ORDER BY c.title", args)
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["Campaign", "Status", "Goal (INR)", "Raised (INR, test)", "Donations", "Tasks", "Tasks completed"])
    for r in rows:
        w.writerow([csv_safe(r["title"]), r["status"], f"{r['goal_amount']:.2f}", f"{r['raised']:.2f}",
                    r["donations"], r["tasks"], r["tasks_done"]])
    return Response(out.getvalue(), mimetype="text/csv", headers={
        "Content-Disposition": 'attachment; filename="campaign-report.csv"'})
