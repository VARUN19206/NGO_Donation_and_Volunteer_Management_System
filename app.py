"""NGO Donation and Volunteer Management System - Module 1 (Authentication).

Run:  python app.py      then open  http://127.0.0.1:5000
"""
import hmac
import secrets

from flask import Flask, abort, request, session

import config
import db
from auth import bp as auth_bp, current_user, nav_for
from campaigns import bp as campaigns_bp, inr, percent
from donations import bp as donations_bp
from tasks import bp as tasks_bp
from updates import bp as updates_bp
from admin import bp as admin_bp


def create_app():
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=config.SECRET_KEY,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        MAX_CONTENT_LENGTH=config.MAX_PHOTO_UPLOAD_BYTES * config.MAX_PHOTOS_PER_UPDATE + 1024 * 1024,
    )
    app.teardown_appcontext(db.close_db)
    app.register_blueprint(auth_bp)
    app.register_blueprint(campaigns_bp)
    app.register_blueprint(donations_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(updates_bp)
    app.register_blueprint(admin_bp)
    app.jinja_env.filters["inr"] = inr
    app.jinja_env.filters["percent"] = percent
    app.jinja_env.globals.update(categories=config.CATEGORIES, role_labels=config.ROLE_LABELS)

    # ---- CSRF protection for every POST form ----
    def csrf_token():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_hex(16)
        return session["csrf_token"]

    @app.before_request
    def check_csrf():
        if request.method == "POST":
            sent = request.form.get("csrf_token", "")
            expected = session.get("csrf_token", "")
            # Both must exist; two empty values must never count as a match.
            if not expected or not sent or not hmac.compare_digest(sent, expected):
                abort(400, description="Form expired. Please go back, refresh the page and try again.")

    @app.context_processor
    def inject_globals():
        return {"csrf_token": csrf_token,
                "nav_user": current_user(),
                "nav_for": nav_for,
                "brand_name": config.BRAND_NAME,
                "brand_short": config.BRAND_SHORT}

    # Stop the browser showing a logged-in page after logout (Back button).
    @app.after_request
    def no_cache(resp):
        if request.endpoint != "static":
            resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.errorhandler(400)
    @app.errorhandler(404)
    @app.errorhandler(413)
    def friendly_error(err):
        from flask import render_template
        return render_template("error.html", code=err.code,
                               message=err.description if err.code == 400 else "The upload is too large. Use smaller photos." if err.code == 413 else
                               "The page you are looking for does not exist."), err.code

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
