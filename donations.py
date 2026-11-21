"""Module 3: donate to a campaign (SIMULATED test transaction), confirmation and history.

No real payment gateway is used. Nothing here charges money.
"""
import re
import secrets
from decimal import Decimal

import pymysql
from flask import (Blueprint, Response, abort, flash, redirect, render_template, request,
                   url_for)

import db
from auth import role_required
from campaigns import get_campaign
from receipt import build_receipt

bp = Blueprint("donations", __name__)

AMOUNT_RE = re.compile(r"^\d{1,8}(\.\d{1,2})?$")
MIN_AMOUNT = Decimal("1")
MAX_AMOUNT = Decimal("10000000")          # 1 crore
QUICK_AMOUNTS = (500, 1000, 2500, 5000)
ONLY_DONORS = "Only donors can make donations. Please log in with a Donor account."


def new_reference():
    """A test reference such as TEST-1A2B3C4D5E (clearly not a real payment id)."""
    return "TEST-" + secrets.token_hex(5).upper()


def parse_amount(text):
    """Return (Decimal or None, error message or None)."""
    text = (text or "").replace(",", "").strip()
    if not AMOUNT_RE.match(text):
        return None, "Enter the amount as a number, for example 500 or 750.50."
    amount = Decimal(text)
    if not MIN_AMOUNT <= amount <= MAX_AMOUNT:
        return None, "Amount must be between ₹1 and ₹1,00,00,000."
    return amount, None


@bp.route("/campaigns/<int:campaign_id>/donate", methods=["GET", "POST"])
@role_required("donor", message=ONLY_DONORS)
def donate(user, campaign_id):
    campaign = get_campaign(campaign_id)
    if campaign is None:
        abort(404)
    if campaign["status"] != "active":
        flash("This campaign is closed and is not accepting donations.", "error")
        return redirect(url_for("campaigns.detail", campaign_id=campaign_id))

    entered = ""
    if request.method == "POST":
        entered = request.form.get("amount", "")
        amount, error = parse_amount(entered)
        if error:
            flash(error, "error")
            return render_template("donate.html", c=campaign, entered=entered,
                                   quick=QUICK_AMOUNTS, active_nav="campaigns"), 400
        donation_id = None
        for _ in range(5):                      # retry in the very unlikely case of a clash
            try:
                donation_id = db.execute(
                    "INSERT INTO donations (campaign_id, donor_id, amount, transaction_ref) "
                    "VALUES (%s, %s, %s, %s)",
                    (campaign_id, user["user_id"], amount, new_reference()))
                break
            except pymysql.err.IntegrityError as exc:
                if "uq_donations_ref" not in str(exc):
                    raise
        if donation_id is None:
            abort(500)
        return redirect(url_for("donations.confirmation", donation_id=donation_id))

    return render_template("donate.html", c=campaign, entered=entered,
                           quick=QUICK_AMOUNTS, active_nav="campaigns")


@bp.route("/donations/<int:donation_id>")
@role_required("donor", message=ONLY_DONORS)
def confirmation(user, donation_id):
    row = db.query_one(
        "SELECT d.donation_id, d.amount, d.transaction_ref, d.created_at, "
        "c.campaign_id, c.title, c.category "
        "FROM donations d JOIN campaigns c ON c.campaign_id = d.campaign_id "
        "WHERE d.donation_id = %s AND d.donor_id = %s", (donation_id, user["user_id"]))
    if row is None:
        abort(404)
    return render_template("donation_confirmation.html", d=row, active_nav="campaigns")


@bp.route("/donor/donations")
@role_required("donor", message=ONLY_DONORS)
def history(user):
    rows = db.all_rows(
        "SELECT d.donation_id, d.amount, d.transaction_ref, d.created_at, "
        "c.campaign_id, c.title "
        "FROM donations d JOIN campaigns c ON c.campaign_id = d.campaign_id "
        "WHERE d.donor_id = %s ORDER BY d.created_at DESC, d.donation_id DESC",
        (user["user_id"],))
    total = sum((r["amount"] for r in rows), Decimal("0"))
    return render_template("donation_history.html", user=user, donations=rows, total=total,
                           active_nav="donations")


@bp.route("/donations/<int:donation_id>/receipt")
@role_required("donor", message=ONLY_DONORS)
def receipt(user, donation_id):
    row = db.query_one(
        "SELECT d.amount, d.transaction_ref, d.created_at, c.title "
        "FROM donations d JOIN campaigns c ON c.campaign_id = d.campaign_id "
        "WHERE d.donation_id = %s AND d.donor_id = %s", (donation_id, user["user_id"]))
    if row is None:
        abort(404)
    pdf = build_receipt(row, user["full_name"], user["email"])
    return Response(pdf, mimetype="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="receipt-{row["transaction_ref"]}.pdf"'})
