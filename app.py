"""NGO Donation and Volunteer Management System - Module 1 (Authentication).

Run:  python app.py      then open  http://127.0.0.1:5000
"""
import hmac
import secrets

from flask import Flask, abort, request, session

import config
import db
from auth import bp as auth_bp


def create_app():
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=config.SECRET_KEY,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )
    app.teardown_appcontext(db.close_db)
    app.register_blueprint(auth_bp)

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
    def friendly_error(err):
        from flask import render_template
        return render_template("error.html", code=err.code,
                               message=err.description if err.code == 400 else
                               "The page you are looking for does not exist."), err.code

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
