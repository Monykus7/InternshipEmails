"""
SimplifyJobs / Pitt CSC Summer 2027 internship list scraper.

Source: https://github.com/SimplifyJobs/Summer2027-Internships
The README uses HTML <tr> rows (not markdown tables) with this structure:

  <tr>
    <td><strong><a href="company_page">Company Name</a></strong></td>
    <td>Job Title</td>
    <td>Location</td>
    <td>...<a href="apply_url">Apply</a>...</td>
    <td>Date Posted</td>
  </tr>

This repo is updated daily by community contributors and Simplify's bot,
making it one of the freshest sources for Summer 2027 intern listings.
"""

import logging
import re

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_README_URL = (
    "https://raw.githubusercontent.com/SimplifyJobs/"
    "Summer2027-Internships/dev/README.md"
)

# Prefer direct application links; fall back to Simplify redirect
_SIMPLIFY_REDIRECT_RE = re.compile(r"utm_source=Simplify")


def _clean_company(cell_text: str) -> str:
    """Strip emoji, '?', and whitespace from company cell text."""
    # Remove common Unicode emoji / symbols prefixed by Simplify
    cleaned = re.sub(r"[^\x00-\x7F]+", "", cell_text).strip()
    return cleaned.strip("?").strip()


def _best_link(td) -> str:
    """
    Return the best apply URL from the Apply <td>.
    Prefers a direct employer link over the Simplify short-link.
    """
    links = td.find_all("a", href=True)
    direct = [a["href"] for a in links if not _SIMPLIFY_REDIRECT_RE.search(a["href"])]
    if direct:
        return direct[0]
    if links:
        return links[0]["href"]
    return ""


def fetch_simplify_jobs(keywords: list[str]) -> list[dict]:
    """
    Parse the SimplifyJobs Summer 2027 GitHub README and return
    keyword-matching internship listings.
    """
    kw_lower = [k.lower() for k in keywords]

    try:
        resp = requests.get(_README_URL, timeout=15)
        resp.raise_for_status()
    except Exception as exc:
        logger.error("Could not fetch SimplifyJobs README: %s", exc)
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    rows = soup.find_all("tr")

    jobs: list[dict] = []
    last_company = ""

    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 4:
            continue

        # ── Company ──────────────────────────────────────────────────────────
        company_td = cells[0]
        company_link = company_td.find("a")
        if company_link:
            raw_company = company_link.get_text(strip=True)
            company = _clean_company(raw_company)
            if company:
                last_company = company
            else:
                company = last_company
        else:
            # Continuation row (same company, different role)
            raw = company_td.get_text(strip=True)
            company = _clean_company(raw) or last_company

        # ── Title ─────────────────────────────────────────────────────────────
        title = cells[1].get_text(separator=" ", strip=True)
        if not title:
            continue

        # ── Location ──────────────────────────────────────────────────────────
        location = cells[2].get_text(separator=", ", strip=True)

        # ── Apply URL ─────────────────────────────────────────────────────────
        apply_td = cells[3]
        url = _best_link(apply_td)
        if not url:
            continue

        # ── Keyword filter ────────────────────────────────────────────────────
        if not any(kw in title.lower() for kw in kw_lower):
            continue

        jobs.append({
            "title": title,
            "company": company,
            "location": location,
            "url": url,
            "source": "SimplifyJobs",
        })

    logger.info("SimplifyJobs → %d keyword-matching listings", len(jobs))
    return jobs
