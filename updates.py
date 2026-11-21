"""Donation impact: campaign admins post updates with photo proof, donors are emailed
and can follow them on the Donation Tracker page."""
import io
import secrets
from html import escape

from flask import (Blueprint, abort, flash, redirect, render_template, request,
                   send_from_directory, url_for)
from PIL import Image, ImageOps, UnidentifiedImageError

import config
import db
import mailer
from auth import role_required
from campaigns import get_campaign, can_edit

bp = Blueprint("updates", __name__)
ADMIN_ROLES = ("campaign_admin", "platform_admin")
Image.MAX_IMAGE_PIXELS = 40_000_000
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_SIDE = 1600
NAME_RE = r"^[0-9a-f]{32}\.jpg$"


class PhotoError(ValueError):
    pass


def process_photo(file_storage):
    """Validate an uploaded picture and return clean JPEG bytes (no EXIF/GPS)."""
    raw = file_storage.read(config.MAX_PHOTO_UPLOAD_BYTES + 1)
    if len(raw) > config.MAX_PHOTO_UPLOAD_BYTES:
        raise PhotoError(f"{file_storage.filename}: photo is larger than 8 MB.")
    try:
        img = Image.open(io.BytesIO(raw))
        if img.format not in ALLOWED_FORMATS:
            raise PhotoError(f"{file_storage.filename}: only JPG, PNG or WEBP photos are allowed.")
        img = ImageOps.exif_transpose(img)
        img.load()
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError):
        raise PhotoError(f"{file_storage.filename or 'File'}: this is not a valid photo.")
    img = img.convert("RGB")
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=85, optimize=True)
    return out.getvalue()


def updates_for(campaign_id, since=None):
    """Updates of a campaign (newest first), each with its list of image file names."""
    sql = ("SELECT u.update_id, u.campaign_id, u.title, u.description, u.amount_used, u.created_at, "
           "a.full_name AS author FROM campaign_updates u JOIN users a ON a.user_id = u.created_by "
           "WHERE u.campaign_id = %s")
    args = [campaign_id]
    if since is not None:
        sql += " AND u.created_at >= %s"
        args.append(since)
    rows = db.all_rows(sql + " ORDER BY u.created_at DESC, u.update_id DESC", args)
    for r in rows:
        r["images"] = [i["filename"] for i in db.all_rows(
            "SELECT filename FROM update_images WHERE update_id = %s ORDER BY image_id", (r["update_id"],))]
    return rows


@bp.route("/uploads/<name>")
def photo(name):
    import re
    if not re.match(NAME_RE, name):
        abort(404)
    return send_from_directory(config.UPLOAD_DIR, name, mimetype="image/jpeg", max_age=3600)


# ---------- admin: post an update ----------

@bp.route("/manage/campaigns/<int:campaign_id>/updates/new", methods=["GET", "POST"])
@role_required(*ADMIN_ROLES)
def create(user, campaign_id):
    campaign = get_campaign(campaign_id)
    if campaign is None:
        abort(404)
    if not can_edit(user, campaign):
        flash("You can only post updates for campaigns that you created.", "error")
        return redirect(url_for("campaigns.manage"))
    donors = db.query_one("SELECT COUNT(DISTINCT d.donor_id) AS n FROM donations d "
                          "JOIN users u ON u.user_id = d.donor_id AND u.is_active = 1 "
                          "WHERE d.campaign_id = %s", (campaign_id,))["n"]

    def page(form, status=200):
        return render_template("update_form.html", user=user, c=campaign, form=form, donors=donors,
                               max_photos=config.MAX_PHOTOS_PER_UPDATE, active_nav="campaigns"), status

    if request.method == "GET":
        return page({})

    title = " ".join(request.form.get("title", "").split())
    description = request.form.get("description", "").replace("\r\n", "\n").strip()
    amount_text = request.form.get("amount_used", "").replace(",", "").strip()
    form = {"title": title, "description": description, "amount_used": amount_text}
    errors = []
    if not 3 <= len(title) <= 120:
        errors.append("Title must be 3 to 120 characters.")
    if not 20 <= len(description) <= 2000:
        errors.append("Description must be 20 to 2000 characters.")
    amount = None
    if amount_text:
        from decimal import Decimal, InvalidOperation
        try:
            amount = Decimal(amount_text)
            if not Decimal("0") < amount <= Decimal("10000000000") or amount.as_tuple().exponent < -2:
                raise InvalidOperation
        except InvalidOperation:
            errors.append("Amount used must be a positive number with up to 2 decimals.")
    files = [f for f in request.files.getlist("photos") if f and f.filename]
    if not files:
        errors.append("Add at least one photo as proof.")
    elif len(files) > config.MAX_PHOTOS_PER_UPDATE:
        errors.append(f"You can add at most {config.MAX_PHOTOS_PER_UPDATE} photos.")
    photos = []
    if not errors:
        try:
            photos = [process_photo(f) for f in files]
        except PhotoError as exc:
            errors.append(str(exc))
    if errors:
        for e in errors:
            flash(e, "error")
        return page(form, 400)

    config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    names = []
    for data in photos:
        name = secrets.token_hex(16) + ".jpg"
        (config.UPLOAD_DIR / name).write_bytes(data)
        names.append(name)
    update_id = db.execute(
        "INSERT INTO campaign_updates (campaign_id, title, description, amount_used, created_by) "
        "VALUES (%s, %s, %s, %s, %s)", (campaign_id, title, description, amount, user["user_id"]))
    for name in names:
        db.execute("INSERT INTO update_images (update_id, filename) VALUES (%s, %s)", (update_id, name))

    sent, saved, failed = notify_donors(campaign, update_id, title, description, amount, names, photos)
    flash("Update posted.", "success")
    parts = []
    if sent:
        parts.append(f"{sent} email(s) sent")
    if saved:
        parts.append(f"{saved} email(s) saved in the outbox folder (SMTP is not configured)")
    if failed:
        parts.append(f"{failed} email(s) failed")
    if parts:
        flash("Donor notifications: " + ", ".join(parts) + ".", "error" if failed else "success")
    else:
        flash("No donors to notify yet.", "success")
    return redirect(url_for("campaigns.detail", campaign_id=campaign_id) + "#updates")


def notify_donors(campaign, update_id, title, description, amount, names, photos):
    recipients = db.all_rows(
        "SELECT DISTINCT u.user_id, u.full_name, u.email FROM donations d "
        "JOIN users u ON u.user_id = d.donor_id WHERE d.campaign_id = %s AND u.is_active = 1",
        (campaign["campaign_id"],))
    counts = {"sent": 0, "saved": 0, "failed": 0}
    if not recipients:
        return 0, 0, 0
    link = f"{config.BASE_URL}/campaigns/{campaign['campaign_id']}#updates"
    images = [(f"photo{i}", data) for i, data in enumerate(photos)]
    amount_line = f"Amount used: Rs. {amount:,.2f}\n" if amount is not None else ""
    try:
        sender = mailer.Sender().__enter__()
    except Exception as exc:                      # SMTP connection or login failed
        for r in recipients:
            db.execute("INSERT INTO email_log (update_id, user_id, status, error) VALUES (%s, %s, 'failed', %s)",
                       (update_id, r["user_id"], str(exc)[:255]))
        return 0, 0, len(recipients)
    try:
        for r in recipients:
            text = (f"Hello {r['full_name']},\n\nAn update was posted for the campaign you supported: "
                    f"{campaign['title']}.\n\n{title}\n{description}\n{amount_line}\n"
                    f"See the photos here: {link}\n\nThis is a college project demo. Donations are simulated.\n")
            html = (f"<div style='font-family:Arial,sans-serif;max-width:560px'>"
                    f"<h2 style='color:#0f2a52'>{escape(title)}</h2>"
                    f"<p>Hello {escape(r['full_name'])}, here is an update from "
                    f"<strong>{escape(campaign['title'])}</strong>, a campaign you supported.</p>"
                    f"<p style='white-space:pre-line'>{escape(description)}</p>"
                    + (f"<p><strong>Amount used:</strong> Rs. {amount:,.2f}</p>" if amount is not None else "")
                    + "".join(f"<img src='cid:{cid}' style='max-width:100%;border-radius:8px;margin:6px 0' alt='Proof photo'>"
                              for cid, _ in images)
                    + f"<p><a href='{escape(link)}'>View on the campaign page</a></p>"
                    f"<p style='color:#777;font-size:12px'>College project demo. Donations are simulated test transactions.</p></div>")
            msg = mailer.build_message(r["email"], f"Update: {title} - {campaign['title']}", text, html, images)
            try:
                status = sender.send(msg)
                err = None
            except Exception as exc:
                status, err = "failed", str(exc)[:255]
            counts[status] += 1
            db.execute("INSERT INTO email_log (update_id, user_id, status, error) VALUES (%s, %s, %s, %s)",
                       (update_id, r["user_id"], status, err))
    finally:
        sender.__exit__()
    return counts["sent"], counts["saved"], counts["failed"]


# ---------- donor: donation tracker ----------

@bp.route("/donor/tracker")
@role_required("donor", message="Only donors can use the Donation Tracker.")
def tracker(user):
    camps = db.all_rows(
        "SELECT c.campaign_id, c.title, c.category, MIN(d.created_at) AS first_at, "
        "SUM(d.amount) AS given, COUNT(*) AS n FROM donations d "
        "JOIN campaigns c ON c.campaign_id = d.campaign_id WHERE d.donor_id = %s "
        "GROUP BY c.campaign_id, c.title, c.category ORDER BY MAX(d.created_at) DESC", (user["user_id"],))
    for c in camps:
        c["updates"] = updates_for(c["campaign_id"], since=c["first_at"])
    return render_template("tracker.html", user=user, camps=camps, active_nav="tracker")
