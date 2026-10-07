"""
Job Digest — entrypoint.

Orchestrates all scrapers, applies filtering and deduplication,
then sends a Gmail digest on every scheduled run, including empty digests.

Usage (local):
    export GMAIL_APP_PASSWORD=<your-16-char-app-password>
    python main.py

For local dev, create a .env file (never commit it):
    echo "GMAIL_APP_PASSWORD=xxxx" > .env
"""

import logging
import sys
from datetime import date

from dotenv import load_dotenv

# Load .env if present (no-op in GitHub Actions where env vars are injected)
load_dotenv()

import config
from core.deduplicator import deduplicate, load_seen, save_seen, merge_job_details
from core.email_sender import send_digest
from core.details import enrich_jobs
from core.filter import filter_jobs, select_best_per_company
from scrapers.greenhouse import fetch_greenhouse_jobs, fetch_lever_jobs
from scrapers.linkedin import fetch_linkedin_jobs
from scrapers.niche_boards import fetch_ros_jobs
from scrapers.simplify_jobs import fetch_simplify_jobs
from scrapers.workday import fetch_workday_jobs

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def main() -> int:
    kw = config.KEYWORDS["roles"]
    all_jobs: list[dict] = []

    # ── SimplifyJobs (best source: community-curated, 300+ 2027 roles) ───────
    if config.SOURCES.get("simplify_jobs"):
        logger.info("── Scraping SimplifyJobs 2027 list …")
        all_jobs += fetch_simplify_jobs(kw)

    # ── LinkedIn ──────────────────────────────────────────────────────────────
    if config.SOURCES.get("linkedin"):
        logger.info("── Scraping LinkedIn …")
        all_jobs += fetch_linkedin_jobs(
            kw, year=config.TARGET_YEAR, season=config.TARGET_SEASON
        )

    # ── Greenhouse ────────────────────────────────────────────────────────────
    if config.SOURCES.get("greenhouse"):
        logger.info("── Scraping Greenhouse …")
        all_jobs += fetch_greenhouse_jobs(config.GREENHOUSE_COMPANIES, kw)

    # ── Lever ─────────────────────────────────────────────────────────────────
    if config.SOURCES.get("lever"):
        logger.info("── Scraping Lever …")
        all_jobs += fetch_lever_jobs(config.LEVER_COMPANIES, kw)

    # ── Workday ───────────────────────────────────────────────────────────────
    if config.SOURCES.get("workday"):
        logger.info("── Scraping Workday …")
        all_jobs += fetch_workday_jobs(config.WORKDAY_COMPANIES, kw)

    # ── Niche boards (ROS Discourse) ─────────────────────────────────────────
    if config.SOURCES.get("niche_boards"):
        logger.info("── Scraping niche boards …")
        all_jobs += fetch_ros_jobs(kw)

    logger.info("Total raw results: %d", len(all_jobs))

    # First discard clear mismatches, then retrieve requirements for remaining
    # unseen candidates before applying the complete applicant profile.
    seen = load_seen()
    filtered = filter_jobs(
        merge_job_details(all_jobs),
        config.KEYWORDS,
        target_year=config.TARGET_YEAR,
        target_season=config.TARGET_SEASON,
        applicant={**config.APPLICANT, "require_description": False},
    )
    candidates, _ = deduplicate(filtered, seen)
    filtered = filter_jobs(
        enrich_jobs(candidates), config.KEYWORDS,
        target_year=config.TARGET_YEAR,
        target_season=config.TARGET_SEASON,
        applicant=config.APPLICANT,
    )
    logger.info("After eligibility screening: %d", len(filtered))

    # ── URL-level deduplication (skip jobs already sent on a previous day) ────
    new_jobs, _ = deduplicate(filtered, seen)
    logger.info("New (unseen) jobs: %d", len(new_jobs))

    # ── Season-aware per-company cap ─────────────────────────────────────────
    cutoff = date.fromisoformat(config.EARLY_SEASON_CUTOFF)
    max_per_co = (
        config.MAX_JOBS_PER_COMPANY_EARLY
        if date.today() < cutoff
        else config.MAX_JOBS_PER_COMPANY_LATE
    )
    logger.info(
        "Per-company cap: %d  (cutoff %s, today %s)",
        max_per_co, cutoff, date.today(),
    )

    # ── Company-level selection: best CS match, season-aware cap ─────────────
    digest_jobs = select_best_per_company(
        new_jobs,
        target_count=config.DIGEST_TARGET_COUNT,
        max_per_company=max_per_co,
    )
    logger.info(
        "Selected %d jobs across %d unique companies for digest.",
        len(digest_jobs),
        len({job["company"].lower() for job in digest_jobs}),
    )

    send_digest(digest_jobs, config.TARGET_EMAIL, config.SENDER_EMAIL)
    # Only successfully delivered listings become seen. Overflow stays available
    # for the next run, and an SMTP failure leaves the cache untouched.
    _, delivered_seen = deduplicate(digest_jobs, seen)
    save_seen(delivered_seen)
    logger.info("Done — sent digest with %d listings.", len(digest_jobs))

    return 0


if __name__ == "__main__":
    sys.exit(main())
