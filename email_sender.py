

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

SENDER_EMAIL = os.environ.get("SENDER_EMAIL")
SENDER_APP_PASSWORD = os.environ.get("SENDER_APP_PASSWORD")
SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = 587

_is_configured = bool(SENDER_EMAIL and SENDER_APP_PASSWORD)


def send_email(to_address, subject, body):
    """
    Sends an actual email if credentials are configured, otherwise
    simulates it (returns a result dict either way so the caller doesn't
    need to know which mode is active).
    """
    if not _is_configured:
        return {
            "sent": False,
            "simulated": True,
            "detail": f"[SIMULATED] Would send to {to_address} — SENDER_EMAIL/SENDER_APP_PASSWORD not set.",
        }

    try:
        msg = MIMEMultipart()
        msg["From"] = SENDER_EMAIL
        msg["To"] = to_address
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_APP_PASSWORD)
            server.sendmail(SENDER_EMAIL, to_address, msg.as_string())

        return {"sent": True, "simulated": False, "detail": f"Email sent to {to_address}."}

    except Exception as e:
        # Never let an email failure crash the recovery flow - log it and
        # let the caller know sending failed, same pattern as the AI
        # message fallback.
        return {"sent": False, "simulated": False, "detail": f"Email failed: {e}"}
