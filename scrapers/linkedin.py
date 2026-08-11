"""
LinkedIn public job search scraper.

Uses LinkedIn's unauthenticated job search URL (no API key required).
Applies exponential backoff with jitter between keyword requests to reduce
the chance of being rate-limited.
"""

import time
import random
import logging
from typing import Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_BASE_URL = (
    "https://www.linkedin.com/jobs/search/"
    "?keywords={kw}"
    "&f_TPR=r86400"   # posted in the last 24 hours
    "&f_JT=I"         # internship job type
)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


def _get_with_backoff(url: str, max_attempts: int = 4) -> Optional[requests.Response]:
    delay = 2.0
    for attempt in range(max_attempts):
        try:
            resp = requests.get(url, headers=_HEADERS, timeout=15)
            if resp.status_code == 200:
                return resp
            logger.warning("LinkedIn returned %s on attempt %d", resp.status_code, attempt + 1)
        except requests.RequestException as exc:
            logger.warning("Request error on attempt %d: %s", attempt + 1, exc)
        # Exponential backoff with ±1 s jitter
        sleep_time = delay + random.uniform(-1, 1)
        time.sleep(max(1.0, sleep_time))
        delay *= 2
    return None


def _parse_cards(soup: BeautifulSoup) -> list[dict]:
    jobs = []
    for card in soup.select("div.base-card"):
        try:
            title_el = card.select_one(".base-search-card__title")
            company_el = card.select_one(".base-search-card__subtitle")
            location_el = card.select_one(".job-search-card__location")
            link_el = card.select_one("a.base-card__full-link")

            if not (title_el and link_el):
                continue

            jobs.append({
                "title": title_el.text.strip(),
                "company": company_el.text.strip() if company_el else "",
                "location": location_el.text.strip() if location_el else "",
                "url": link_el["href"].split("?")[0],  # strip tracking params
                "source": "LinkedIn",
            })
        except Exception as exc:  # noqa: BLE001
            logger.debug("Failed to parse LinkedIn card: %s", exc)
    return jobs


def fetch_linkedin_jobs(
    keywords: list[str],
    year: str = "2027",
    season: str = "summer",
) -> list[dict]:
    """
    Fetch internship listings from LinkedIn for each keyword.

    Appends *year* and *season* to every search query so LinkedIn's own
    relevance ranking surfaces cohort-specific postings first.
    """
    all_jobs: list[dict] = []
    for kw in keywords:
        # e.g. "software engineer intern 2027 summer"
        full_query = f"{kw} {year} {season}"
        encoded = full_query.replace(" ", "%20")
        url = _BASE_URL.format(kw=encoded)
        resp = _get_with_backoff(url)
        if resp is None:
            logger.error("Skipping LinkedIn keyword '%s' after repeated failures.", kw)
            continue
        soup = BeautifulSoup(resp.text, "lxml")
        jobs = _parse_cards(soup)
        logger.info("LinkedIn '%s' → %d results", kw, len(jobs))
        all_jobs.extend(jobs)
        # Polite delay between keyword searches
        time.sleep(random.uniform(2, 5))
    return all_jobs
