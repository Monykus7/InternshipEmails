"""
Job deduplicator backed by a JSON file in data/seen_jobs.json.

Each entry records the MD5 of the job URL and the ISO date it was first seen.
Entries older than MAX_AGE_DAYS are purged on every save to keep the file lean.
"""

import hashlib
import json
import logging
import pathlib
from datetime import date, timedelta

logger = logging.getLogger(__name__)

CACHE_FILE = pathlib.Path("data/seen_jobs.json")
MAX_AGE_DAYS = 30


def _job_id(job: dict) -> str:
    return hashlib.md5(job["url"].encode()).hexdigest()


def load_seen() -> dict[str, str]:
    """Load the seen-jobs cache. Returns {job_id: iso_date_string}."""
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logger.warning("seen_jobs.json is corrupt — starting fresh.")
    return {}


def save_seen(seen: dict[str, str]) -> None:
    """Persist the cache, purging entries older than MAX_AGE_DAYS."""
    cutoff = date.today() - timedelta(days=MAX_AGE_DAYS)
    pruned = {
        jid: seen_date
        for jid, seen_date in seen.items()
        if date.fromisoformat(seen_date) >= cutoff
    }
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(pruned, indent=2), encoding="utf-8")
    logger.info("Saved %d seen-job entries (%d pruned).", len(pruned), len(seen) - len(pruned))


def deduplicate(
    jobs: list[dict], seen: dict[str, str]
) -> tuple[list[dict], dict[str, str]]:
    """
    Remove jobs already present in *seen* and record new ones.

    Returns:
        (new_jobs, updated_seen)
    """
    today = date.today().isoformat()
    new_jobs: list[dict] = []
    for job in jobs:
        jid = _job_id(job)
        if jid not in seen:
            new_jobs.append(job)
            seen[jid] = today
    return new_jobs, seen
