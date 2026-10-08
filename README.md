# Summer 2027 Internship Digest

Find US software engineering, ML, data science and robotics internships for a CS bachelor's student, and email a digest every six hours via GitHub Actions.

Each email contains **0–20 new matching jobs**. Twenty is a maximum, never a minimum. Empty runs send a brief no-matches email. Companies contribute up to two jobs before December 1, 2026, and one afterwards.

Jobs must have a reported **original publication date within the last 24 hours**. The finder reads employer `JobPosting.datePosted`, LinkedIn's posting-date element, or an RSS publication timestamp. Unknown/invalid dates, future dates and dates older than the rolling window are excluded. Discovery times, Greenhouse `updated_at`, and community-list age are not substitutes for an original posting date. Date-only values are interpreted as midnight UTC, which can conservatively omit recent posts from the previous calendar day; the email labels these as date-only. Publisher-provided timestamps remain the source of truth.

## How screening works

The finder requires an internship title and positive US location evidence, rejects explicitly different internship years/seasons, and checks readable employer requirements for advanced-degree and incompatible-major requirements. Simplify's advanced-degree, citizenship, sponsorship and closed-application markers are preserved. Employer application links are preferred over aggregator links.

Requirements come from Greenhouse/Lever APIs or public employer pages (structured JobPosting data and supported description selectors). Postings with unreadable requirements are excluded by default. Bare `Remote`, `See posting` and unknown locations are excluded because US eligibility cannot be confirmed.

This is a conservative text filter. Requirement wording varies, and passing the filter does not establish every aspect of eligibility. Graduation dates and enrollment conditions still need checking. The applicant is not a US citizen, so citizenship-required jobs are excluded. US-person/export-control restrictions are also excluded unless that separate eligibility is confirmed in the profile. Sponsorship restrictions are labelled until that status is configured. Missing internship-term information is also labelled.

Configure your profile in [config.py](config.py):

```python
APPLICANT = {
    "degree_level": "bachelors",
    "us_only": True,
    "major": "computer science",
    "needs_sponsorship": None,  # True or False when known
    "us_citizen": False,
    "us_person": None,          # Unknown; export-restricted jobs are excluded
    "require_description": True,
}
DIGEST_TARGET_COUNT = 20
MAX_POSTING_AGE_HOURS = 24
```

The cache records **only successfully emailed jobs**. Jobs above the digest/company cap remain eligible for later runs; SMTP failure leaves the cache unchanged. Tracking parameters are ignored for deduplication, while job-identifying parameters such as `gh_jid` are preserved. Entries expire after 30 days, so still-open jobs can reappear after that period. Cache entries already recorded by older versions cannot distinguish sent jobs from discarded overflow.

## Local setup

Use Python 3.11 or later:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium
```

Set `TARGET_EMAIL` and `SENDER_EMAIL` in the environment or `config.py`. Create a Gmail App Password for the sender account and put it in a local `.env` file:

```text
GMAIL_APP_PASSWORD=your-app-password
```

`.env` must remain uncommitted. See [Google's App Password instructions](https://support.google.com/accounts/answer/185833).

Run tests without sending email:

```powershell
python -m unittest discover -s tests -v
```

Run the finder and send a real email:

```powershell
python main.py
```

## Scheduled delivery

The workflow is [.github/workflows/daily_digest.yml](.github/workflows/daily_digest.yml), named **Internship Digest (Every 6 Hours)**.

1. Put the updated workflow and source on the repository's default branch.
2. Add the `GMAIL_APP_PASSWORD` repository secret in **Settings → Secrets and variables → Actions**.
3. Use **Actions → Internship Digest (Every 6 Hours) → Run workflow** to verify delivery.

The UTC schedule is **01:17, 07:17, 13:17 and 19:17**. Pacific times are 12:17 AM, 6:17 AM, 12:17 PM and 6:17 PM during daylight saving time; they shift one hour earlier during standard time. Scheduling away from the start of the hour reduces contention. GitHub schedules can still be delayed or skipped, and scheduled workflows run only from the default branch; see [GitHub's schedule documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).

Concurrent workflow runs are serialized to protect delivery state. Each successful run commits `data/seen_jobs.json` back to the repository. Playwright system dependencies are installed on every fresh runner, even when browser downloads are cached.

## Project files

- `main.py`: scraper orchestration, screening, selection, delivery and cache updates.
- `config.py`: applicant profile, target term, keywords, sources and company lists.
- `core/filter.py`: eligibility screening and per-company ranking.
- `core/details.py`: public employer requirement retrieval.
- `core/freshness.py`: original publication date parsing and rolling 24-hour filtering.
- `core/text.py`: HTML requirement-text extraction.
- `core/deduplicator.py`: sent-job cache and URL deduplication.
- `core/email_sender.py`, `templates/digest.html`: HTML and plain-text email.
- `scrapers/`: SimplifyJobs, LinkedIn, Greenhouse, Lever, Workday and ROS sources.
- `tests/test_finder.py`: filtering, scraper parsing, empty digests, overflow and SMTP failure checks.

## Troubleshooting

- **No jobs in an email:** inspect `Filter exclusions` and `Retrieved requirements` logs. A sparse digest is expected when requirements or US locations cannot be verified.
- **Old postings:** inspect `Posting-age exclusions`; only jobs with qualifying original publication dates can be sent. The email displays the date and its source.
- **SMTP authentication fails:** check the Gmail App Password for the sender account.
- **Workday fails:** check its site path, browser installation and system dependencies. The current scraper only inspects the first results page; pagination and searching internships directly would improve coverage.
- **LinkedIn returns no jobs:** public search may be blocked. Its job cards need employer requirements enrichment before they can pass strict screening.
- **Repeat jobs after a month:** the cache has a 30-day retention window; increase `MAX_AGE_DAYS` in `core/deduplicator.py` if desired.
