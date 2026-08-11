"""
Keyword-based job filter with cohort-year awareness and company-level selection.

Pass 1 — seniority exclusion:  drop titles with "senior", "lead", "phd", etc.
Pass 2 — role inclusion:        keep titles matching a role keyword.
Pass 3 — cohort year filter:    keep postings for the target year;
                                 drop postings that explicitly name a *different* year.
                                 Postings with NO year in the title are always kept.

select_best_per_company() then picks the single best-matching role per company
and caps the result at a target count, ensuring digest variety.
"""

import re

# Higher-priority role fragments for a junior CS student.
# A job whose title matches more of these gets surfaced first when a company
# has multiple open intern roles.
_PRIORITY_FRAGMENTS = [
    "software engineer",
    "software engineering",
    "machine learning",
    "computer vision",
    "deep learning",
    "robotics",
    "autonomy",
    "perception",
    "data science",
    "backend",
    "frontend",
    "full stack",
    "research engineer",
    "ai",
    "ml",
]


def _extract_years(text: str) -> list[str]:
    """Return all 4-digit years found in *text*."""
    return re.findall(r"\b(20\d{2})\b", text)


def _relevance_score(title: str) -> int:
    """
    Score a job title for relevance to a junior CS student.
    Higher = better match. Used to pick the best role when a company
    has multiple intern postings.
    """
    t = title.lower()
    return sum(1 for frag in _PRIORITY_FRAGMENTS if frag in t)


def filter_jobs(
    jobs: list[dict],
    keywords: dict,
    target_year: str | None = None,
    target_season: str | None = None,
) -> list[dict]:
    """
    Filter a list of job dicts.

    Args:
        jobs:          Raw job list from scrapers.
        keywords:      Dict with "roles" (include) and "exclude" keys.
        target_year:   e.g. "2027". Jobs that name a *different* year are dropped.
                       Jobs with no year in the title are kept.
        target_season: e.g. "summer". Informational only; LinkedIn query handles
                       season filtering upstream.

    Returns:
        Filtered list of jobs (may still contain multiple per company).
    """
    include_terms = [k.lower() for k in keywords["roles"]]
    exclude_terms = [k.lower() for k in keywords["exclude"]]

    filtered = []
    for job in jobs:
        title_lower = job["title"].lower()

        # Pass 1: seniority / non-student exclusion
        if any(term in title_lower for term in exclude_terms):
            continue

        # Pass 2: role inclusion
        if not any(term in title_lower for term in include_terms):
            continue

        # Pass 3: cohort year filter
        if target_year:
            years_in_title = _extract_years(title_lower)
            if years_in_title and target_year not in years_in_title:
                continue

        filtered.append(job)

    return filtered


def select_best_per_company(
    jobs: list[dict],
    target_count: int = 20,
    max_per_company: int = 1,
) -> list[dict]:
    """
    Return up to *target_count* jobs, at most *max_per_company* per company.

    Selection strategy:
    1. Group jobs by company name (case-insensitive).
    2. Within each company, rank by relevance score and keep the top
       *max_per_company* roles (best CS match first).
    3. Sort all kept jobs by score (descending) so the most relevant roles
       appear first in the digest.
    4. Cap at *target_count*.

    Setting max_per_company=2 during early recruiting season lets you see
    multiple strong roles from a company that just dropped a batch of listings,
    while max_per_company=1 later keeps the digest diversified.
    """
    company_map: dict[str, list[dict]] = {}
    for job in jobs:
        key = job["company"].lower().strip()
        company_map.setdefault(key, []).append(job)

    selected: list[dict] = []
    for company_jobs in company_map.values():
        # Sort within company by relevance, take the top N
        ranked = sorted(company_jobs, key=lambda j: _relevance_score(j["title"]), reverse=True)
        for job in ranked[:max_per_company]:
            job["_score"] = _relevance_score(job["title"])
            selected.append(job)

    # Sort globally by score descending, then alphabetically for ties
    selected.sort(key=lambda j: (-j["_score"], j["company"].lower()))

    result = selected[:target_count]
    for job in result:
        job.pop("_score", None)

    return result
