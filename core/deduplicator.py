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
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

logger = logging.getLogger(__name__)

CACHE_FILE = pathlib.Path("data/seen_jobs.json")
MAX_AGE_DAYS = 30


def _job_id(job: dict) -> str:
    parts = urlsplit(job["url"])
    query = [(key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True)
             if not key.lower().startswith("utm_") and key.lower() not in {"ref", "source", "referrer"}]
    url = urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"),
                     urlencode(sorted(query)), ""))
    return hashlib.md5(url.encode()).hexdigest()


def merge_job_details(jobs: list[dict]) -> list[dict]:
    """Combine duplicate source metadata before screening or fetching details."""
    merged = {}
    for job in jobs:
        jid = _job_id(job)
        previous = merged.get(jid, {})
        combined = {**previous, **job}
        if previous.get("description") and not job.get("description"):
            combined["description"] = previous["description"]
        for key in ("advanced_degree_required", "no_sponsorship", "us_citizenship_required", "is_closed"):
            if previous.get(key) or job.get(key):
                combined[key] = True
        merged[jid] = combined
    return list(merged.values())


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
    updated_seen = seen.copy()
    new_jobs: list[dict] = []
    for job in jobs:
        jid = _job_id(job)
        legacy_id = hashlib.md5(job["url"].encode()).hexdigest()
        if jid not in updated_seen and legacy_id not in updated_seen:
            new_jobs.append(job)
            updated_seen[jid] = today
    return new_jobs, updated_seen
