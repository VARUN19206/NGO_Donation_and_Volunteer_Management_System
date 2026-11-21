"""Email sending. If SMTP_HOST is set the mail is sent for real; otherwise each
email is saved as an .eml file in the outbox folder (open it with any mail app)."""
import re
import smtplib
import ssl
from datetime import datetime
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

import config


def build_message(to_addr, subject, text, html, images=()):
    """images: list of (cid, bytes) JPEG pictures shown inside the HTML body."""
    msg = EmailMessage()
    msg["From"] = config.SMTP_FROM
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid()
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")
    html_part = msg.get_payload()[1]
    for cid, data in images:
        html_part.add_related(data, maintype="image", subtype="jpeg", cid=f"<{cid}>")
    return msg


class Sender:
    """Opens one SMTP connection (or none, for the outbox) and sends many mails."""

    def __init__(self):
        self.smtp = None

    def __enter__(self):
        if config.SMTP_HOST:
            self.smtp = smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=15)
            if config.SMTP_TLS:
                self.smtp.starttls(context=ssl.create_default_context())
            if config.SMTP_USER:
                self.smtp.login(config.SMTP_USER, config.SMTP_PASSWORD)
        return self

    def __exit__(self, *exc):
        if self.smtp:
            try:
                self.smtp.quit()
            except Exception:
                pass

    def send(self, msg):
        """Returns 'sent' or 'saved'. Raises on failure."""
        if self.smtp:
            self.smtp.send_message(msg)
            return "sent"
        config.OUTBOX_DIR.mkdir(parents=True, exist_ok=True)
        safe = re.sub(r"[^A-Za-z0-9]+", "_", msg["To"])[:40]
        name = f"{datetime.now():%Y%m%d-%H%M%S-%f}-{safe}.eml"
        (config.OUTBOX_DIR / name).write_bytes(bytes(msg))
        return "saved"
