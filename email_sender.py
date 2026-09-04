"""
email_sender.py
-----------------
Sends the actual recovery email using Python's built-in smtplib (no extra
libraries needed). Uses Gmail's SMTP server as an example, but any SMTP
provider works the same way.

WHY THIS IS SAFE TO DEMO WITH:
If you haven't set up email credentials, this automatically falls back to
"simulation mode" - it prints what WOULD have been sent instead of actually
sending, so the app never crashes and you can demo without setting anything
up. Once you add real credentials, it starts actually sending.

HOW TO ENABLE REAL SENDING (optional, takes 5 minutes):
1. Use a Gmail account (or any email provider that supports SMTP).
2. For Gmail specifically: go to https://myaccount.google.com/apppasswords
   and generate an "App Password" (NOT your normal Gmail password - Gmail
   blocks normal passwords for this).
3. Set two environment variables before running the app:
     SENDER_EMAIL = your gmail address
     SENDER_APP_PASSWORD = the 16-character app password you generated
   On Mac/Linux (in the terminal, before running python3 app.py):
     export SENDER_EMAIL="youraddress@gmail.com"
     export SENDER_APP_PASSWORD="abcd efgh ijkl mnop"
   On Windows (Command Prompt):
     set SENDER_EMAIL=youraddress@gmail.com
     set SENDER_APP_PASSWORD=abcdefghijklmnop

IMPORTANT FOR THE DEMO: don't email real companies' real inboxes during a
live demo. Use your own email address as the "customer_contact" for test
invoices, or just leave credentials unset and let it simulate - simulation
mode is completely fine to show judges; you can explain "in production this
would use SMTP, here's the exact code that does it."
"""

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
