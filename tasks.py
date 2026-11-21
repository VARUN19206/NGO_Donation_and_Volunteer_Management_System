"""Module 4: volunteer tasks.

Admins create tasks for a campaign and assign them to a volunteer.
Volunteers see their own tasks and update the status.
"""
from datetime import date, datetime

from flask import (Blueprint, abort, flash, redirect, render_template, request,
                   url_for)

import config
import db
from auth import role_required
from campaigns import get_campaign, can_edit

bp = Blueprint("tasks", __name__)

ADMIN_ROLES = ("campaign_admin", "platform_admin")

TASK_SELECT = (
    "SELECT t.task_id, t.campaign_id, t.title, t.description, t.due_date, t.assigned_to, "
    "t.status, t.created_by, t.created_at, c.title AS campaign_title, "
    "c.created_by AS campaign_owner, v.full_name AS volunteer_name, v.email AS volunteer_email "
    "FROM tasks t JOIN campaigns c ON c.campaign_id = t.campaign_id "
    "JOIN users v ON v.user_id = t.assigned_to ")

STATUS_ORDER = "FIELD(t.status, 'pending', 'in_progress', 'completed')"
SORT = f"ORDER BY {STATUS_ORDER}, t.due_date IS NULL, t.due_date, t.task_id DESC"


def get_task(task_id):
    return db.query_one(TASK_SELECT + "WHERE t.task_id = %s", (task_id,))


def can_manage(user, task):
    return user["role"] == "platform_admin" or task["campaign_owner"] == user["user_id"]


def form_options(user):
    """Campaigns this admin may add tasks to, and the active volunteers."""
    if user["role"] == "platform_admin":
        campaigns = db.all_rows("SELECT campaign_id, title FROM campaigns ORDER BY title")
    else:
        campaigns = db.all_rows("SELECT campaign_id, title FROM campaigns WHERE created_by = %s ORDER BY title",
                                (user["user_id"],))
    volunteers = db.all_rows("SELECT user_id, full_name, email FROM users "
                             "WHERE role = 'volunteer' AND is_active = 1 ORDER BY full_name")
    return campaigns, volunteers


def validate_task(form, user, editing):
    title = " ".join(form.get("title", "").split())
    description = form.get("description", "").replace("\r\n", "\n").strip()
    due_text = form.get("due_date", "").strip()
    status = form.get("status", "pending") if editing else "pending"
    errors = []

    if not 3 <= len(title) <= 120:
        errors.append("Task title must be 3 to 120 characters.")
    if not 10 <= len(description) <= 1000:
        errors.append("Task description must be 10 to 1000 characters.")

    campaign = None
    try:
        campaign = get_campaign(int(form.get("campaign_id", "")))
    except ValueError:
        pass
    if campaign is None or not can_edit(user, campaign):
        errors.append("Choose one of your campaigns.")
        campaign = None

    volunteer = None
    try:
        volunteer = db.query_one("SELECT user_id FROM users WHERE user_id = %s "
                                 "AND role = 'volunteer' AND is_active = 1", (int(form.get("assigned_to", "")),))
    except ValueError:
        pass
    if volunteer is None:
        errors.append("Choose a volunteer.")

    due = None
    if due_text:
        try:
            due = datetime.strptime(due_text, "%Y-%m-%d").date()
        except ValueError:
            errors.append("Enter the due date as day-month-year using the date picker.")
        else:
            if not editing and due < date.today():
                errors.append("The due date cannot be in the past.")
    if status not in config.TASK_STATUSES:
        errors.append("Choose a valid status.")

    values = {"title": title, "description": description, "due_date": due_text, "status": status,
              "campaign_id": form.get("campaign_id", ""), "assigned_to": form.get("assigned_to", "")}
    return values, campaign, volunteer, due, errors


# ---------- admin: manage tasks ----------

@bp.route("/manage/tasks")
@role_required(*ADMIN_ROLES)
def manage(user):
    if user["role"] == "platform_admin":
        rows = db.all_rows(TASK_SELECT + SORT)
    else:
        rows = db.all_rows(TASK_SELECT + "WHERE c.created_by = %s " + SORT, (user["user_id"],))
    return render_template("manage_tasks.html", user=user, tasks=rows, today=date.today(),
                           statuses=config.TASK_STATUSES, active_nav="tasks")


@bp.route("/manage/tasks/new", methods=["GET", "POST"])
@role_required(*ADMIN_ROLES)
def create(user):
    campaigns, volunteers = form_options(user)
    if request.method == "POST":
        values, campaign, volunteer, due, errors = validate_task(request.form, user, editing=False)
        if not errors:
            db.execute(
                "INSERT INTO tasks (campaign_id, title, description, due_date, assigned_to, created_by) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (campaign["campaign_id"], values["title"], values["description"], due,
                 volunteer["user_id"], user["user_id"]))
            flash("Task created and assigned.", "success")
            return redirect(url_for("tasks.manage"))
        for e in errors:
            flash(e, "error")
        return render_template("task_form.html", user=user, form=values, editing=False,
                               campaigns=campaigns, volunteers=volunteers, today=date.today(),
                               statuses=config.TASK_STATUSES, active_nav="tasks"), 400
    return render_template("task_form.html", user=user, form={}, editing=False, campaigns=campaigns,
                           volunteers=volunteers, today=date.today(), statuses=config.TASK_STATUSES,
                           active_nav="tasks")


@bp.route("/manage/tasks/<int:task_id>/edit", methods=["GET", "POST"])
@role_required(*ADMIN_ROLES)
def edit(user, task_id):
    task = get_task(task_id)
    if task is None:
        abort(404)
    if not can_manage(user, task):
        flash("You can only edit tasks of campaigns that you created.", "error")
        return redirect(url_for("tasks.manage"))
    campaigns, volunteers = form_options(user)

    if request.method == "POST":
        values, campaign, volunteer, due, errors = validate_task(request.form, user, editing=True)
        if not errors:
            db.execute(
                "UPDATE tasks SET campaign_id = %s, title = %s, description = %s, due_date = %s, "
                "assigned_to = %s, status = %s WHERE task_id = %s",
                (campaign["campaign_id"], values["title"], values["description"], due,
                 volunteer["user_id"], values["status"], task_id))
            flash("Task updated.", "success")
            return redirect(url_for("tasks.manage"))
        for e in errors:
            flash(e, "error")
        return render_template("task_form.html", user=user, form=values, editing=True,
                               campaigns=campaigns, volunteers=volunteers, today=date.today(),
                               statuses=config.TASK_STATUSES, active_nav="tasks"), 400

    form = {"title": task["title"], "description": task["description"],
            "due_date": task["due_date"].isoformat() if task["due_date"] else "",
            "status": task["status"], "campaign_id": str(task["campaign_id"]),
            "assigned_to": str(task["assigned_to"])}
    return render_template("task_form.html", user=user, form=form, editing=True, campaigns=campaigns,
                           volunteers=volunteers, today=date.today(), statuses=config.TASK_STATUSES,
                           active_nav="tasks")


# ---------- volunteer: my tasks ----------

@bp.route("/volunteer/tasks")
@role_required("volunteer")
def mine(user):
    rows = db.all_rows(TASK_SELECT + "WHERE t.assigned_to = %s " + SORT, (user["user_id"],))
    groups = {key: [r for r in rows if r["status"] == key] for key in config.TASK_STATUSES}
    return render_template("volunteer_tasks.html", user=user, groups=groups, total=len(rows),
                           today=date.today(), statuses=config.TASK_STATUSES, active_nav="tasks")


@bp.route("/volunteer/tasks/<int:task_id>/status", methods=["POST"])
@role_required("volunteer")
def set_status(user, task_id):
    task = db.query_one("SELECT task_id FROM tasks WHERE task_id = %s AND assigned_to = %s",
                        (task_id, user["user_id"]))
    if task is None:
        abort(404)
    status = request.form.get("status", "")
    if status not in config.TASK_STATUSES:
        flash("Choose a valid status.", "error")
    else:
        db.execute("UPDATE tasks SET status = %s WHERE task_id = %s", (status, task_id))
        flash(f"Task marked as {config.TASK_STATUSES[status].lower()}.", "success")
    return redirect(url_for("tasks.mine"))
