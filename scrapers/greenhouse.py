"""
Greenhouse and Lever scrapers.

Both platforms expose a free, public JSON API — no login required.
  Greenhouse: https://boards-api.greenhouse.io/v1/boards/{company}/jobs
  Lever:      https://api.lever.co/v0/postings/{company}?mode=json
"""

import logging

import requests
from core.filter import matches_role
from core.text import html_text

logger = logging.getLogger(__name__)

_GREENHOUSE_BASE = "https://boards-api.greenhouse.io/v1/boards/{company}/jobs?content=true"
_LEVER_BASE = "https://api.lever.co/v0/postings/{company}?mode=json"


def fetch_greenhouse_jobs(companies: list[str], keywords: list[str]) -> list[dict]:
    """Return keyword-matching jobs from Greenhouse for every listed company."""
    jobs: list[dict] = []

    for company in companies:
        url = _GREENHOUSE_BASE.format(company=company)
        try:
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            data = response.json()
            for job in data.get("jobs", []):
                title = job.get("title", "")
                if not matches_role(title, keywords):
                    continue
                jobs.append({
                    "title": title,
                    "company": company.replace("-", " ").title(),
                    "location": job.get("location", {}).get("name", ""),
                    "url": job.get("absolute_url", ""),
                    "source": "Greenhouse",
                    "description": html_text(job.get("content", "")),
                })
        except Exception as exc:  # noqa: BLE001
            logger.warning("Greenhouse error for '%s': %s", company, exc)

    logger.info("Greenhouse → %d results across %d companies", len(jobs), len(companies))
    return jobs


def fetch_lever_jobs(companies: list[str], keywords: list[str]) -> list[dict]:
    """Return keyword-matching jobs from Lever for every listed company."""
    jobs: list[dict] = []

    for company in companies:
        url = _LEVER_BASE.format(company=company)
        try:
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            postings = resp.json()

            # Lever returns a list on success; a dict like {'ok': False, 'error': '...'}
            # on failure (e.g. unknown company slug).
            if not isinstance(postings, list):
                logger.warning(
                    "Lever unexpected response for '%s' (slug may be wrong): %s",
                    company,
                    postings,
                )
                continue

            for posting in postings:
                if not isinstance(posting, dict):
                    continue
                title = posting.get("text", "")
                if not matches_role(title, keywords):
                    continue
                jobs.append({
                    "title": title,
                    "company": company.replace("-", " ").title(),
                    "location": posting.get("categories", {}).get("location", ""),
                    "url": posting.get("hostedUrl", ""),
                    "source": "Lever",
                    "description": html_text(
                        posting.get("description", "") + "\n" + "\n".join(
                            section.get("text", "") + "\n" + section.get("content", "")
                            for section in posting.get("lists", [])
                        ) + "\n" + posting.get("additional", ""),
                    ),
                })
        except Exception as exc:  # noqa: BLE001
            logger.warning("Lever error for '%s': %s", company, exc)

    logger.info("Lever → %d results across %d companies", len(jobs), len(companies))
    return jobs
