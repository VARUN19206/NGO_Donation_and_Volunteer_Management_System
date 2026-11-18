"""Module 1: registration, login, logout and role-based access."""
import re
from functools import wraps

import pymysql
from flask import (Blueprint, flash, redirect, render_template, request,
                   session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

import config
import db

bp = Blueprint("auth", __name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
NAME_RE = re.compile(r"^[A-Za-z][A-Za-z .'-]{1,99}$")
HASH_METHOD = "pbkdf2:sha256"
# Used when the email is not found, so the response time looks the same.
DUMMY_HASH = generate_password_hash("not-a-real-password", method=HASH_METHOD)

# Each role's dashboard page. Later modules add their links here.
HOME_ENDPOINT = {
    "donor": "auth.donor_dashboard",
    "volunteer": "auth.volunteer_dashboard",
    "campaign_admin": "auth.admin_dashboard",
    "platform_admin": "auth.admin_dashboard",
}

ROLE_INFO = {
    "donor": "You can see your account here. Browsing campaigns, donating and your donation history come in the next modules.",
    "volunteer": "You can see your account here. Volunteer tasks come in the next modules.",
    "campaign_admin": "You can see your account here. Creating and managing campaigns comes in the next modules.",
    "platform_admin": "You can see your account here. Managing users and records comes in the next modules.",
}


# ---------- helpers ----------

def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    return db.query_one(
        "SELECT user_id, full_name, email, role, created_at FROM users "
        "WHERE user_id = %s AND is_active = 1", (uid,))


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if user is None:
            session.clear()
            flash("Please log in to continue.", "info")
            return redirect(url_for("auth.login"))
        return view(user, *args, **kwargs)
    return wrapped


def role_required(*roles):
    def decorator(view):
        @login_required
        @wraps(view)
        def wrapped(user, *args, **kwargs):
            if user["role"] not in roles:
                flash("You do not have access to that page.", "error")
                return redirect(url_for(HOME_ENDPOINT[user["role"]]))
            return view(user, *args, **kwargs)
        return wrapped
    return decorator


def validate_registration(form):
    """Return (cleaned_values, list_of_errors)."""
    name = " ".join(form.get("full_name", "").split())
    email = form.get("email", "").strip().lower()
    password = form.get("password", "")
    confirm = form.get("confirm_password", "")
    role = form.get("role", "")
    errors = []

    if not NAME_RE.match(name):
        errors.append("Enter your full name (letters only, at least 2 characters).")
    if len(email) > 120 or not EMAIL_RE.match(email):
        errors.append("Enter a valid email address.")
    if len(password) < 8 or not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        errors.append("Password must be at least 8 characters and contain a letter and a number.")
    elif len(password) > 128:
        errors.append("Password is too long (maximum 128 characters).")
    elif password != confirm:
        errors.append("Passwords do not match.")
    if role not in config.SELF_REGISTER_ROLES:
        errors.append("Choose Donor or Volunteer.")
    return {"full_name": name, "email": email, "password": password, "role": role}, errors


# ---------- pages ----------

@bp.route("/")
def index():
    user = current_user()
    if user:
        return redirect(url_for(HOME_ENDPOINT[user["role"]]))
    return redirect(url_for("auth.login"))


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user():
        return redirect(url_for("auth.index"))

    selected = request.values.get("role", "donor")
    if selected not in config.SELF_REGISTER_ROLES:
        selected = "donor"

    if request.method == "POST":
        values, errors = validate_registration(request.form)
        selected = values["role"] if values["role"] in config.SELF_REGISTER_ROLES else selected
        if not errors:
            try:
                db.execute(
                    "INSERT INTO users (full_name, email, password_hash, role) "
                    "VALUES (%s, %s, %s, %s)",
                    (values["full_name"], values["email"],
                     generate_password_hash(values["password"], method=HASH_METHOD),
                     values["role"]),
                )
            except pymysql.err.IntegrityError:
                errors.append("An account with this email already exists. Please log in.")
            else:
                flash("Account created. Please log in.", "success")
                tab = values["role"]
                return redirect(url_for("auth.login", role=tab))
        for e in errors:
            flash(e, "error")
        return render_template("register.html", selected=selected,
                               form=values), 400
    return render_template("register.html", selected=selected, form={})


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user():
        return redirect(url_for("auth.index"))

    selected = request.values.get("role", "donor")
    if selected not in config.TAB_ROLES:
        selected = "donor"

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = db.query_one(
            "SELECT user_id, password_hash, role, is_active FROM users WHERE email = %s",
            (email,))
        stored = user["password_hash"] if user else DUMMY_HASH
        password_ok = check_password_hash(stored, password)
        allowed = (user is not None and password_ok and user["is_active"]
                   and user["role"] in config.TAB_ROLES[selected])
        if allowed:
            session.clear()                      # new session after login
            session["user_id"] = user["user_id"]
            return redirect(url_for(HOME_ENDPOINT[user["role"]]))
        # One message for every failure so nothing is revealed about accounts.
        flash("Invalid email or password for the selected role.", "error")
        return render_template("login.html", selected=selected,
                               email=email), 401
    return render_template("login.html", selected=selected, email="")


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("auth.login"))


# ---------- role dashboards (Module 1 shows account details only) ----------

def _dashboard(user, active):
    return render_template("dashboard.html", user=user, active=active,
                           role_label=config.ROLE_LABELS[user["role"]],
                           role_info=ROLE_INFO[user["role"]])


@bp.route("/donor")
@role_required("donor")
def donor_dashboard(user):
    return _dashboard(user, "donor")


@bp.route("/volunteer")
@role_required("volunteer")
def volunteer_dashboard(user):
    return _dashboard(user, "volunteer")


@bp.route("/admin")
@role_required("campaign_admin", "platform_admin")
def admin_dashboard(user):
    return _dashboard(user, "admin")
