"""
Gmail SMTP email sender.

Sends an HTML digest with a plain-text fallback so mail clients that
don't render HTML still show something useful.
"""

import logging
import os
import smtplib
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger(__name__)

_SMTP_HOST = "smtp.gmail.com"
_SMTP_PORT = 465


def _build_plain_text(jobs: list[dict]) -> str:
    lines = [f"Daily Internship Digest — {date.today().strftime('%B %d, %Y')}", ""]
    for job in jobs:
        lines += [
            job["title"],
            f"  Company:  {job['company']}",
            f"  Location: {job['location']}",
            f"  Source:   {job['source']}",
            f"  URL:      {job['url']}",
            "",
        ]
    lines.append("Disable the GitHub Actions workflow to stop receiving these emails.")
    return "\n".join(lines)


def send_digest(jobs: list[dict], to_email: str, from_email: str) -> None:
    """
    Render the HTML template and send the digest via Gmail SMTP.

    Requires the GMAIL_APP_PASSWORD environment variable to be set.
    """
    app_password = os.environ.get("GMAIL_APP_PASSWORD")
    if not app_password:
        raise EnvironmentError(
            "GMAIL_APP_PASSWORD environment variable is not set. "
            "Create a Gmail App Password and export it before running."
        )

    env = Environment(loader=FileSystemLoader("templates"), autoescape=True)
    template = env.get_template("digest.html")
    html_body = template.render(jobs=jobs, date=date.today().strftime("%B %d, %Y"))
    plain_body = _build_plain_text(jobs)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = (
        f"\U0001f916 Summer 2027 Internship Digest \u2014 {len(jobs)} new listings ({date.today()})"
    )
    msg["From"] = from_email
    msg["To"] = to_email

    # Plain-text part first; mail clients prefer the last part they can render
    msg.attach(MIMEText(plain_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP_SSL(_SMTP_HOST, _SMTP_PORT) as server:
        server.login(from_email, app_password)
        server.sendmail(from_email, to_email, msg.as_string())

    logger.info("Digest sent to %s (%d jobs).", to_email, len(jobs))
