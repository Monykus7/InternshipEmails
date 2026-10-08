"""Screen explicit restrictions; flag requirements that remain unverified."""

import logging
import re
from collections import Counter
from urllib.parse import urlsplit

logger = logging.getLogger(__name__)

_PRIORITY_FRAGMENTS = [
    "software engineer", "software engineering", "machine learning",
    "computer vision", "deep learning", "robotics", "autonomy", "perception",
    "data science", "backend", "frontend", "full stack", "research engineer", "ai", "ml",
]
_US_STATES = "AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC".split()
_US_CITIES = {
    "sf", "nyc", "san francisco", "new york", "seattle", "boston", "austin",
    "chicago", "los angeles", "san jose", "san diego", "mountain view", "palo alto",
    "sunnyvale", "santa clara", "menlo park", "redmond", "bellevue", "atlanta",
}
_US_STATE_NAMES = (
    "alabama|alaska|arizona|arkansas|california|colorado|connecticut|delaware|florida|"
    "georgia|hawaii|idaho|illinois|indiana|iowa|kansas|kentucky|louisiana|maine|maryland|"
    "massachusetts|michigan|minnesota|mississippi|missouri|montana|nebraska|nevada|"
    "new hampshire|new jersey|new mexico|new york|north carolina|north dakota|ohio|"
    "oklahoma|oregon|pennsylvania|rhode island|south carolina|south dakota|tennessee|"
    "texas|utah|vermont|virginia|washington|west virginia|wisconsin|wyoming"
)


def _normalize(text: str) -> str:
    t = re.sub(r"[-_/–—]", " ", text.lower())
    t = re.sub(r"\binternships?\b", "intern", t)
    return re.sub(r"\s+", " ", t).strip()


def _contains(text: str, term: str) -> bool:
    return bool(re.search(r"(?<!\w)" + re.escape(_normalize(term)) + r"(?!\w)", text))


def matches_role(title: str, keywords: list[str]) -> bool:
    return any(_contains(_normalize(title), term) for term in keywords)


def _relevance_score(title: str) -> int:
    t = _normalize(title)
    return sum(_contains(t, fragment) for fragment in _PRIORITY_FRAGMENTS)


def is_us_location(location: str) -> bool:
    """Require positive US location evidence, including remote jobs.

    Bare 'Remote' is unknown, not permission to work remotely from the US.
    City aliases are intentionally limited; ambiguous locations are excluded.
    """
    if re.search(r"\b(?:united states(?: of america)?|usa|u\.s\.?|us)\b", location, re.I):
        return True
    # State abbreviations need a city/comma prefix to avoid 'CA' (Canada).
    if re.search(r",\s*(?:" + "|".join(_US_STATES) + r")\b", location):
        return True
    if re.search(r"\b(?:" + _US_STATE_NAMES + r")\b", location, re.I):
        # Georgia and Washington alone are ambiguous; require a US context.
        if location.strip().lower() not in {"georgia", "washington"}:
            return True
    return location.strip().lower() in _US_CITIES


def _sentences(description: str) -> list[str]:
    return re.split(r"[\n;]|(?<=[.!?])\s+(?=[A-Z])", description)


def _advanced_degree_only(title: str, description: str, degree: str | None) -> bool:
    if not degree or degree == "phd":
        return False
    advanced = r"\b(?:ph\.?\s*d\.?|doctoral|doctorate|master['’]?s?|m\.?s\.?|mba)\b"
    bachelor = r"\b(?:bachelor['’]?s?|undergraduate|b\.?s\.?|b\.?a\.?)\b"
    if re.search(advanced, title, re.I) and not re.search(bachelor, title, re.I):
        if degree == "bachelors" or re.search(r"ph\.?\s*d|doctoral|doctorate", title, re.I):
            return True
    for sentence in _sentences(description):
        if re.search(r"\b(?:preferred|preference|ideally)\b", sentence, re.I):
            continue
        if re.search(bachelor, sentence, re.I):
            continue
        if degree == "masters" and re.search(r"master['’]?s?", sentence, re.I):
            continue
        if re.search(advanced, sentence, re.I) and re.search(
            r"\b(?:required|must|pursuing|enrolled|working towards|candidate|students?)\b", sentence, re.I
        ):
            return True
    return False


def _other_major_required(description: str, major: str | None) -> bool:
    if major != "computer science":
        return False
    other = r"\b(?:mechanical engineering|electrical engineering|civil engineering|chemical engineering|aerospace engineering|biomedical engineering|biology|chemistry|physics|neuroscience|mathematics|statistics|economics|finance|accounting|business administration|marketing)\b"
    compatible = r"\b(?:computer science|computing|software engineering|computer engineering)\b"
    for sentence in _sentences(description):
        if re.search(r"\b(?:preferred|ideally)\b", sentence, re.I):
            continue
        if re.search(other, sentence, re.I) and not re.search(compatible, sentence, re.I):
            if re.search(r"\b(?:degree|major|pursuing|enrolled|studying)\b", sentence, re.I):
                return True
    return False


def _screen(job: dict, keywords: dict, target_year: str | None,
            target_season: str | None, applicant: dict) -> tuple[str | None, list[str]]:
    title = job.get("title", "")
    t = _normalize(title)
    description = job.get("description", "")
    text = _normalize(title + " " + description)
    notes = []
    url = urlsplit(job.get("url", ""))
    if url.scheme not in {"https", "http"} or not url.netloc or job.get("is_closed"):
        return "closed or missing application link", notes
    # Always require an internship in the title. Full-time hours during an
    # internship are acceptable; 'full time' in the description is not a ban.
    if not re.search(r"\bintern\b", t) or re.search(r"\b(?:new grad|graduate program|permanent)\b", t):
        return "not an internship", notes
    exclusions = [term for term in keywords["exclude"] if term not in {"phd", "doctoral"}]
    if any(_contains(t, term) for term in exclusions):
        return "seniority or excluded role", notes
    if not matches_role(title, keywords["roles"]):
        return "role mismatch", notes
    years = re.findall(r"\b20\d{2}\b", t)
    if target_year and years and str(target_year) not in years:
        return "different internship year", notes
    seasons = set(re.findall(r"\b(?:summer|fall|autumn|winter|spring)\b", t))
    seasons = {"fall" if season == "autumn" else season for season in seasons}
    target = "fall" if target_season == "autumn" else target_season
    if target and seasons and target.lower() not in seasons:
        return "different internship season", notes
    # Don't interpret graduation years as internship years.
    terms = re.findall(r"\b(summer|fall|autumn|winter|spring)\s+(20\d{2})\b", text)
    if not seasons and terms and target and target_year:
        if not any(("fall" if s == "autumn" else s) == target and y == str(target_year) for s, y in terms):
            return "different internship term in description", notes
    degree = applicant.get("degree_level")
    if (job.get("advanced_degree_required") and degree == "bachelors") or _advanced_degree_only(title, description, degree):
        return "advanced degree required", notes
    if _other_major_required(description, applicant.get("major")):
        return "different major required", notes
    if applicant.get("us_only") and not is_us_location(job.get("location", "")):
        return "non-US or unknown location", notes
    no_sponsorship = job.get("no_sponsorship") or bool(re.search(
        r"\b(?:no (?:visa )?sponsorship|(?:cannot|will not|do not|does not|unable to) "
        r"(?:offer|provide|support)(?:\s+\w+){0,5}\s+(?:sponsorship|visas?)|"
        r"without (?:the need for )?(?:visa )?sponsorship)\b", text))
    # Explicitly optional citizenship must not exclude otherwise eligible jobs.
    citizenship_text = re.sub(
        r"(?:do not|does not|doesn't|don't|not) require(?:s)? (?:current )?(?:u\.?s\.?|united states) citizenship|"
        r"no (?:u\.?s\.?|united states) citizenship (?:is )?required", "", text
    )
    citizen_only = job.get("us_citizenship_required") or bool(re.search(
        r"(?:must be (?:an? )?(?:u\.?s\.?|united states) citizen|"
        r"(?:u\.?s\.?|united states) citizenship (?:is )?required|"
        r"(?:requires?|must have) (?:current )?(?:u\.?s\.?|united states) citizenship|"
        r"(?:u\.?s\.?|united states) citizenship (?:is )?(?:mandatory|necessary)|"
        r"(?:u\.?s\.?|united states) citizens only)", citizenship_text))
    us_person_required = bool(re.search(
        r"(?:must|requires?|need to|have to)(?:\s+\w+){0,6}\s+(?:a )?u\.?s\.? person|"
        r"u\.?s\.? person(?:\s+\w+){0,5}\s+(?:required|requirement)|"
        r"applicants must qualify as a u\.?s\.? person", text))
    if no_sponsorship:
        if applicant.get("needs_sponsorship") is True:
            return "no sponsorship", notes
        if applicant.get("needs_sponsorship") is None:
            notes.append("No sponsorship offered; confirm work authorization.")
    if citizen_only:
        if applicant.get("us_citizen") is False:
            return "US citizenship required", notes
        if applicant.get("us_citizen") is None:
            notes.append("US citizenship required; confirm eligibility.")
    if us_person_required:
        if applicant.get("us_person") is not True:
            return "US-person/export-control eligibility not confirmed", notes
    # A noncitizen shouldn't receive a role whose citizenship requirement
    # depends on an unspecified contract. This is uncertainty, not a claim
    # that every export-controlled role requires citizenship.
    if applicant.get("us_citizen") is False and re.search(
        r"some positions(?:\s+\w+){0,6}\s+require(?:\s+\w+){0,3}\s+u\.?s\.? citizenship", text
    ):
        return "possible contract citizenship requirement", notes
    if not description:
        if applicant.get("require_description"):
            return "requirements unavailable", notes
        notes.append("Requirements unavailable; verify degree, major and work authorization.")
    else:
        notes.append("Check graduation-date and enrollment requirements before applying.")
    term_confirmed = (target_year in years and target in seasons) if target_year and target else False
    term_confirmed = term_confirmed or any(s == target and y == target_year for s, y in terms)
    term_confirmed = term_confirmed or (job.get("cohort_year") == target_year and job.get("cohort_season") == target)
    if not term_confirmed:
        notes.append("Internship year/season not confirmed in posting.")
    return None, notes


def filter_jobs(jobs: list[dict], keywords: dict, target_year: str | None = None,
                target_season: str | None = None, applicant: dict | None = None) -> list[dict]:
    filtered = []
    rejected = Counter()
    for job in jobs:
        reason, notes = _screen(job, keywords, target_year, target_season, applicant or {})
        if reason:
            rejected[reason] += 1
        else:
            filtered.append({**job, "eligibility_notes": notes})
    logger.info("Filter exclusions: %s", dict(rejected))
    return filtered


def select_best_per_company(jobs: list[dict], target_count: int = 20,
                            max_per_company: int = 1) -> list[dict]:
    company_map: dict[str, list[dict]] = {}
    for job in jobs:
        key = job.get("company", "").lower().strip()
        if not key or key == "see posting":
            key = job["url"]
        company_map.setdefault(key, []).append(job)
    selected = []
    for company_jobs in company_map.values():
        ranked = sorted(company_jobs, key=lambda j: _relevance_score(j["title"]), reverse=True)
        selected.extend(ranked[:max_per_company])
    selected.sort(key=lambda j: (-_relevance_score(j["title"]), j["company"].lower()))
    return selected[:target_count]
