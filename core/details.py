"""Retrieve requirements from public job pages before eligibility screening."""

import json
import logging
from concurrent.futures import ThreadPoolExecutor

import requests
from bs4 import BeautifulSoup
from core.text import html_text

logger = logging.getLogger(__name__)


def _job_posting(value):
    if isinstance(value, dict):
        kind = value.get("@type", [])
        if kind == "JobPosting" or (isinstance(kind, list) and "JobPosting" in kind):
            yield value
        for child in value.values():
            yield from _job_posting(child)
    elif isinstance(value, list):
        for child in value:
            yield from _job_posting(child)


def parse_details(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            postings = list(_job_posting(json.loads(script.get_text())))
        except (ValueError, TypeError):
            continue
        # A page listing multiple jobs isn't a single job description.
        if len(postings) == 1 and postings[0].get("description"):
            posting = postings[0]
            details = {"description": html_text(posting["description"])}
            locations = posting.get("jobLocation", [])
            if isinstance(locations, dict):
                locations = [locations]
            names = []
            for location in locations:
                if not isinstance(location, dict):
                    continue
                address = location.get("address", {})
                if isinstance(address, dict):
                    names.append(", ".join(str(address[key]) for key in
                                          ("addressLocality", "addressRegion", "addressCountry") if address.get(key)))
            if names:
                details["location"] = "; ".join(names)
            return details
    for selector in (
        "#content", ".job__description", ".posting-page .section-wrapper",
        "[data-automation-id='jobPostingDescription']", ".show-more-less-html__markup",
        ".job-description", "#job-description", "[itemprop='description']",
    ):
        blocks = soup.select(selector)
        if blocks:
            return {"description": "\n".join(html_text(str(block)) for block in blocks)}
    return {}


def _enrich(job: dict) -> dict:
    if job.get("description"):
        return job
    try:
        response = requests.get(job["url"], timeout=12, headers={"User-Agent": "InternshipDigest/1.0"})
        if response.status_code in {404, 410}:
            return {**job, "is_closed": True}
        response.raise_for_status()
        details = parse_details(response.text)
        # Prefer the employer's structured location when available.
        return {**job, **details}
    except requests.RequestException as exc:
        logger.warning("Requirements unavailable for %s (%s)", job["url"], type(exc).__name__)
        return job


def enrich_jobs(jobs: list[dict]) -> list[dict]:
    """Bound concurrency/timeouts and fetch once per application URL."""
    unique = {}
    for job in jobs:
        if job["url"] not in unique or job.get("description"):
            unique[job["url"]] = job
    with ThreadPoolExecutor(max_workers=6) as pool:
        enriched = list(pool.map(_enrich, unique.values()))
    logger.info("Retrieved requirements for %d/%d candidates.",
                sum(bool(job.get("description")) for job in enriched), len(enriched))
    return enriched
