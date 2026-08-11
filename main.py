"""
Job Digest — entrypoint.

Orchestrates all scrapers, applies filtering and deduplication,
then sends a Gmail digest if new listings are found.

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
from core.deduplicator import deduplicate, load_seen, save_seen
from core.email_sender import send_digest
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

    # ── Keyword + year filter ─────────────────────────────────────────────────
    filtered = filter_jobs(
        all_jobs,
        config.KEYWORDS,
        target_year=config.TARGET_YEAR,
        target_season=config.TARGET_SEASON,
    )
    logger.info("After keyword + year filter: %d", len(filtered))

    # ── URL-level deduplication (skip jobs already sent on a previous day) ────
    seen = load_seen()
    new_jobs, updated_seen = deduplicate(filtered, seen)
    logger.info("New (unseen) jobs: %d", len(new_jobs))

    # Save ALL new jobs to the cache now (including ones we won't email today),
    # so tomorrow's digest only shows truly fresh postings.
    save_seen(updated_seen)

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
        len(digest_jobs),
    )

    if digest_jobs:
        send_digest(digest_jobs, config.TARGET_EMAIL, config.SENDER_EMAIL)
        logger.info("Done — sent digest with %d listings.", len(digest_jobs))
    else:
        logger.info("No new listings today — no email sent.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
