"""
Gmail SMTP email sender.

Sends an HTML digest with a plain-text fallback so mail clients that
don't render HTML still show something useful.
"""

import logging
import os
import smtplib
from datetime import datetime, timezone
from pathlib import Path
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import format_datetime, make_msgid

from jinja2 import Environment, FileSystemLoader
import config

logger = logging.getLogger(__name__)

_SMTP_HOST = "smtp.gmail.com"
_SMTP_PORT = 465


def _build_plain_text(jobs: list[dict]) -> str:
    lines = [f"Internship Digest — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}", ""]
    if not jobs:
        lines.append(f"No new matching internships with a reported posting date in the last {config.MAX_POSTING_AGE_HOURS} hours. The finder checks every six hours.")
    for job in jobs:
        lines += [
            job["title"],
            f"  Company:  {job['company']}",
            f"  Location: {job['location']}",
            f"  Source:   {job['source']}",
            f"  URL:      {job['url']}",
            f"  Posted:   {job.get('posting_date_label', 'Unknown')} ({job.get('posting_date_source', 'Unknown source')})",
            "",
        ]
        lines.extend(f"  Check: {note}" for note in job.get("eligibility_notes", []))
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

    env = Environment(loader=FileSystemLoader(Path(__file__).resolve().parent.parent / "templates"), autoescape=True)
    template = env.get_template("digest.html")
    sent_time = datetime.now(timezone.utc)
    sent_at = sent_time.strftime("%Y-%m-%d %H:%M:%S UTC")
    html_body = template.render(jobs=jobs, date=sent_at, freshness_hours=config.MAX_POSTING_AGE_HOURS)
    plain_body = _build_plain_text(jobs)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = (
        f"\U0001f916 Summer 2027 Internship Digest \u2014 {len(jobs)} new listings ({sent_at})"
    )
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Date"] = format_datetime(sent_time)
    msg["Message-ID"] = make_msgid(domain=from_email.rsplit("@", 1)[-1])

    # Plain-text part first; mail clients prefer the last part they can render
    msg.attach(MIMEText(plain_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP_SSL(_SMTP_HOST, _SMTP_PORT) as server:
        server.login(from_email, app_password)
        server.sendmail(from_email, to_email, msg.as_string())

    logger.info("Digest sent to %s (%d jobs).", to_email, len(jobs))
