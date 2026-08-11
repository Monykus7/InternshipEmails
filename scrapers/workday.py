"""
Workday scraper using Playwright (headless Chromium).

Workday career pages are JS-rendered, so a real browser is needed.

Config format (WORKDAY_COMPANIES):
    List of (display_name, subdomain, career_site_path) triples.
    The full URL tried is:
        https://{subdomain}.wd{n}.myworkdayjobs.com/en-US/{career_site_path}
    where n is tried as 1, 3, 5 in order.

Each company's career_site_path is the last segment of their Workday URL,
e.g. "Northrop_Grumman_External_Site" for Northrop Grumman.
"""

import logging

from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)

_WD_NUMBERS = ["wd1", "wd3", "wd5"]
_JOB_TITLE_SELECTOR = "[data-automation-id='jobTitle']"

# Realistic browser context settings to avoid bot-detection 406s
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


def _try_load(page, subdomain: str, site_path: str) -> str | None:
    """
    Try wd1 → wd3 → wd5 with the given site_path.
    Returns the first URL whose page successfully renders job title elements.
    """
    for wdn in _WD_NUMBERS:
        url = f"https://{subdomain}.{wdn}.myworkdayjobs.com/en-US/{site_path}"
        try:
            page.goto(url, timeout=25_000, wait_until="domcontentloaded")
            page.wait_for_selector(_JOB_TITLE_SELECTOR, timeout=12_000)
            return url
        except PlaywrightTimeout:
            logger.debug("Workday selector timeout: %s", url)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Workday load error (%s): %s", url, exc)
    return None


def fetch_workday_jobs(
    companies: list[tuple[str, str, str]], keywords: list[str]
) -> list[dict]:
    """
    Scrape Workday career pages.

    Args:
        companies: List of (display_name, subdomain, career_site_path) triples,
                   as defined in config.WORKDAY_COMPANIES.
        keywords:  Role keyword strings to match against job titles.
    """
    kw_lower = [k.lower() for k in keywords]
    jobs: list[dict] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=_USER_AGENT,
            locale="en-US",
        )
        page = ctx.new_page()

        for company_name, subdomain, site_path in companies:
            resolved_url = _try_load(page, subdomain, site_path)
            if resolved_url is None:
                logger.warning(
                    "Could not load Workday page for '%s' (sub=%s, path=%s). "
                    "The site_path in WORKDAY_COMPANIES may be wrong.",
                    company_name,
                    subdomain,
                    site_path,
                )
                continue

            try:
                company_job_count = 0
                cards = page.query_selector_all(_JOB_TITLE_SELECTOR)
                for card in cards:
                    title = card.inner_text().strip()
                    if any(kw in title.lower() for kw in kw_lower):
                        # Try to get a direct link to the posting
                        link_el = card.query_selector("a")
                        job_url = resolved_url
                        if link_el:
                            href = link_el.get_attribute("href")
                            if href:
                                job_url = href if href.startswith("http") else f"https://{subdomain}.wd1.myworkdayjobs.com{href}"
                        jobs.append({
                            "title": title,
                            "company": company_name,
                            "location": "",
                            "url": job_url,
                            "source": "Workday",
                        })
                        company_job_count += 1
                logger.info("Workday '%s' → %d matches", company_name, company_job_count)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Error parsing Workday results for '%s': %s", company_name, exc)

        browser.close()

    logger.info("Workday total → %d jobs", len(jobs))
    return jobs
