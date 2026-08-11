"""
Greenhouse and Lever scrapers.

Both platforms expose a free, public JSON API — no login required.
  Greenhouse: https://boards-api.greenhouse.io/v1/boards/{company}/jobs
  Lever:      https://api.lever.co/v0/postings/{company}?mode=json
"""

import logging

import requests

logger = logging.getLogger(__name__)

_GREENHOUSE_BASE = "https://boards-api.greenhouse.io/v1/boards/{company}/jobs?content=true"
_LEVER_BASE = "https://api.lever.co/v0/postings/{company}?mode=json"


def fetch_greenhouse_jobs(companies: list[str], keywords: list[str]) -> list[dict]:
    """Return keyword-matching jobs from Greenhouse for every listed company."""
    jobs: list[dict] = []
    kw_lower = [k.lower() for k in keywords]

    for company in companies:
        url = _GREENHOUSE_BASE.format(company=company)
        try:
            data = requests.get(url, timeout=15).json()
            for job in data.get("jobs", []):
                title = job.get("title", "")
                if not any(kw in title.lower() for kw in kw_lower):
                    continue
                jobs.append({
                    "title": title,
                    "company": company.replace("-", " ").title(),
                    "location": job.get("location", {}).get("name", ""),
                    "url": job.get("absolute_url", ""),
                    "source": "Greenhouse",
                })
        except Exception as exc:  # noqa: BLE001
            logger.warning("Greenhouse error for '%s': %s", company, exc)

    logger.info("Greenhouse → %d results across %d companies", len(jobs), len(companies))
    return jobs


def fetch_lever_jobs(companies: list[str], keywords: list[str]) -> list[dict]:
    """Return keyword-matching jobs from Lever for every listed company."""
    jobs: list[dict] = []
    kw_lower = [k.lower() for k in keywords]

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
                if not any(kw in title.lower() for kw in kw_lower):
                    continue
                jobs.append({
                    "title": title,
                    "company": company.replace("-", " ").title(),
                    "location": posting.get("categories", {}).get("location", ""),
                    "url": posting.get("hostedUrl", ""),
                    "source": "Lever",
                })
        except Exception as exc:  # noqa: BLE001
            logger.warning("Lever error for '%s': %s", company, exc)

    logger.info("Lever → %d results across %d companies", len(jobs), len(companies))
    return jobs
