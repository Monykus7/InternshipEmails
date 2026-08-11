"""
Niche robotics / ML job board scrapers.

Current sources:
  - ROS Discourse jobs category (public RSS feed)
"""

import logging

import feedparser

logger = logging.getLogger(__name__)

_ROS_RSS = "https://discourse.ros.org/c/jobs/15.rss"


def fetch_ros_jobs(keywords: list[str]) -> list[dict]:
    """Parse the ROS Discourse jobs RSS feed and filter by keyword."""
    kw_lower = [k.lower() for k in keywords]
    jobs: list[dict] = []

    try:
        feed = feedparser.parse(_ROS_RSS)
        for entry in feed.entries:
            title = entry.get("title", "")
            summary = entry.get("summary", "")
            # Match on title or post body so niche postings with creative titles aren't missed
            searchable = (title + " " + summary).lower()
            if any(kw in searchable for kw in kw_lower):
                jobs.append({
                    "title": title,
                    "company": "See posting",
                    "location": "See posting",
                    "url": entry.get("link", ""),
                    "source": "ROS Discourse",
                })
    except Exception as exc:  # noqa: BLE001
        logger.warning("ROS Discourse feed error: %s", exc)

    logger.info("ROS Discourse → %d matches", len(jobs))
    return jobs
