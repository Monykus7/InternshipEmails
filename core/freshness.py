"""Screen by reported original publication time, never discovery/update time."""

import logging
from collections import Counter
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)


def parse_posted_at(value: str | None) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        # ISO dates without a clock are conservatively treated as midnight UTC.
        posted = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if posted.tzinfo is None:
        posted = posted.replace(tzinfo=timezone.utc)
    return posted.astimezone(timezone.utc)


def filter_recent_jobs(jobs: list[dict], max_age_hours: int = 24,
                       now: datetime | None = None) -> list[dict]:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("Freshness checks require a timezone-aware current time")
    cutoff = now - timedelta(hours=max_age_hours)
    recent = []
    rejected = Counter()
    for job in jobs:
        posted = parse_posted_at(job.get("posted_at"))
        if posted is None:
            rejected["original posting date unavailable"] += 1
        elif posted > now:
            rejected["future posting date"] += 1
        elif posted < cutoff:
            rejected["older than freshness window"] += 1
        else:
            recent.append({
                **job,
                "posting_date_label": posted.strftime("%Y-%m-%d %H:%M UTC")
                    + (" (date only)" if len(job["posted_at"].strip()) == 10 else ""),
            })
    logger.info("Posting-age exclusions: %s; %d within last %d hours.",
                dict(rejected), len(recent), max_age_hours)
    return recent
