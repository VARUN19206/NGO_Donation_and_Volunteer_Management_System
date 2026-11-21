"""PDF receipt for a donation. These are TEST receipts: no real payment is made."""
import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

import config

NAVY = colors.HexColor("#0f2a52")
BLUE = colors.HexColor("#1f6feb")
GREY = colors.HexColor("#5b6b82")


def rupees(amount):
    """Indian digit grouping. The built-in PDF font has no rupee sign, so 'Rs.' is used."""
    whole, _, frac = f"{amount:.2f}".partition(".")
    head, tail = whole[:-3], whole[-3:]
    parts = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    if head:
        parts.insert(0, head)
    return "Rs. " + ",".join(parts + [tail]) + "." + frac


def build_receipt(d, donor_name, donor_email):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4, pageCompression=0)
    c.setTitle(f"Donation receipt {d['transaction_ref']}")
    c.setAuthor(config.BRAND_NAME)
    w, h = A4
    left, right = 20 * mm, w - 20 * mm

    c.setFillColor(NAVY)
    c.rect(0, h - 38 * mm, w, 38 * mm, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 17)
    c.drawString(left, h - 18 * mm, config.BRAND_NAME)
    c.setFont("Helvetica", 11)
    c.drawString(left, h - 27 * mm, "Donation Receipt")

    y = h - 52 * mm
    c.setFillColor(colors.HexColor("#fff3dc"))
    c.setStrokeColor(colors.HexColor("#e0a100"))
    c.rect(left, y - 12 * mm, right - left, 14 * mm, stroke=1, fill=1)
    c.setFillColor(colors.HexColor("#8a5300"))
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(w / 2, y - 3 * mm, "NGO Donation Recipt")
    c.setFont("Helvetica", 9)
    c.drawString(left + 4 * mm, y - 8 * mm,
                 "Thank you for your generous donation")

    y -= 28 * mm
    rows = [("Receipt / test reference", d["transaction_ref"]),
            ("Date and time", d["created_at"].strftime("%d %b %Y, %I:%M %p")),
            ("Donor", donor_name),
            ("Donor email", donor_email),
            ("Campaign", d["title"])]
    for label, value in rows:
        c.setFillColor(GREY)
        c.setFont("Helvetica", 10)
        c.drawString(left, y, label)
        c.setFillColor(NAVY)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(left + 55 * mm, y, str(value)[:70])
        c.setStrokeColor(colors.HexColor("#e3e9f2"))
        c.line(left, y - 3 * mm, right, y - 3 * mm)
        y -= 11 * mm

    y -= 4 * mm
    c.setFillColor(colors.HexColor("#e8f5ee"))
    c.rect(left, y - 8 * mm, right - left, 18 * mm, stroke=0, fill=1)
    c.setFillColor(GREY)
    c.setFont("Helvetica", 10)
    c.drawString(left + 4 * mm, y + 2 * mm, "Amount donated (test)")
    c.setFillColor(colors.HexColor("#0b6e47"))
    c.setFont("Helvetica-Bold", 20)
    c.drawRightString(right - 4 * mm, y - 3 * mm, rupees(d["amount"]))

    c.setFillColor(GREY)
    c.setFont("Helvetica", 9)
    c.drawString(left, 30 * mm, "Thank you for supporting our mission. This receipt was generated automatically.")
    c.drawString(left, 25 * mm, "It is part of a college project demo and carries no legal or financial value.")
    c.showPage()
    c.save()
    return buf.getvalue()
