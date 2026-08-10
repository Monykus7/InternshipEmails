# 📬 Job Digest Email System — Cursor Build Plan

A daily email digest that scrapes internship postings for **SWE, Data Science, and Robotics** roles from LinkedIn, Greenhouse/Lever, Workday, and niche robotics boards — then sends them to your Gmail each morning via GitHub Actions.

---

## 🗂️ Project Structure

```
job-digest/
├── .github/
│   └── workflows/
│       └── daily_digest.yml       # GitHub Actions cron schedule
├── scrapers/
│   ├── __init__.py
│   ├── linkedin.py                # LinkedIn scraper
│   ├── greenhouse.py              # Greenhouse/Lever scraper
│   ├── workday.py                 # Workday scraper
│   └── niche_boards.py            # Robotics-specific boards
├── core/
│   ├── __init__.py
│   ├── deduplicator.py            # Avoids re-sending seen jobs
│   ├── filter.py                  # Keyword + seniority filtering
│   └── email_sender.py            # Gmail SMTP sender
├── templates/
│   └── digest.html                # HTML email template
├── data/
│   └── seen_jobs.json             # Persisted job ID cache (committed to repo)
├── config.py                      # Keywords, sources, targets
├── main.py                        # Entrypoint — orchestrates all scrapers
├── requirements.txt
└── README.md
```

---

## ⚙️ Phase 1 — Project Setup

### 1.1 Initialize the repo
- Create a new GitHub repo: `job-digest`
- Clone it locally and open in Cursor
- Create the folder structure above

### 1.2 Install dependencies
Add to `requirements.txt`:
```
requests
beautifulsoup4
lxml
selenium          # fallback for JS-heavy pages
playwright        # preferred for Workday (JS-rendered)
jinja2            # HTML email templating
python-dotenv
```

Install with:
```bash
pip install -r requirements.txt
playwright install chromium
```

### 1.3 Create `config.py`
```python
# config.py

TARGET_EMAIL = "your@gmail.com"
SENDER_EMAIL = "your@gmail.com"
# SENDER_APP_PASSWORD loaded from env

KEYWORDS = {
    "roles": [
        "software engineer intern", "SWE intern",
        "data science intern", "data scientist intern",
        "machine learning intern", "ML intern",
        "robotics software intern", "robotics engineer intern",
        "robot perception intern", "autonomy intern",
    ],
    "exclude": ["senior", "staff", "principal", "lead", "manager", "director"],
}

SOURCES = {
    "linkedin": True,
    "greenhouse": True,
    "lever": True,
    "workday": True,
    "niche_boards": True,
}

# Greenhouse/Lever: companies with known robotics/ML internship programs
GREENHOUSE_COMPANIES = [
    "openai", "scale-ai", "cohere", "waymo",
    "nuro", "zoox", "cruise", "aurora", "kodiak-robotics",
]

LEVER_COMPANIES = [
    "anduril", "skydio", "boston-dynamics", "sarcos",
]

WORKDAY_COMPANIES = [
    # (company_name, workday_subdomain)
    ("Boston Dynamics", "bostondynamics"),
    ("Intuitive Surgical", "intuitivesurgical"),
    ("Northrop Grumman", "northropgrumman"),
    ("Lockheed Martin", "lmco"),
    ("Raytheon", "rtx"),
]

NICHE_BOARDS = [
    "https://www.robotics-worldwide.org/jobs/",
    "https://jobs.lever.co/",     # searched by keyword
    # Add more as needed
]
```

---

## 🕷️ Phase 2 — Scrapers

### 2.1 `scrapers/linkedin.py`
LinkedIn does **not** allow direct scraping via API for free. Use one of two approaches:

**Option A (recommended for beginners): RSS / Google hack**
```python
# Use Google's site: search trick or LinkedIn's public job search URL
# No login required for basic results

import requests
from bs4 import BeautifulSoup

def fetch_linkedin_jobs(keywords: list[str]) -> list[dict]:
    jobs = []
    for keyword in keywords:
        url = (
            "https://www.linkedin.com/jobs/search/"
            f"?keywords={keyword.replace(' ', '%20')}"
            "&f_TPR=r86400"   # posted in last 24 hours
            "&f_JT=I"         # internship type
        )
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, "lxml")
        cards = soup.select("div.base-card")
        for card in cards:
            title = card.select_one(".base-search-card__title")
            company = card.select_one(".base-search-card__subtitle")
            location = card.select_one(".job-search-card__location")
            link = card.select_one("a.base-card__full-link")
            if title and link:
                jobs.append({
                    "title": title.text.strip(),
                    "company": company.text.strip() if company else "",
                    "location": location.text.strip() if location else "",
                    "url": link["href"],
                    "source": "LinkedIn",
                })
    return jobs
```

> ⚠️ **Cursor Prompt:** "LinkedIn may block scraping. Add exponential backoff with random delays between 2–5 seconds between requests. Also add a `try/except` around each card parse so one failure doesn't kill the whole batch."

---

### 2.2 `scrapers/greenhouse.py`
Greenhouse has a **public JSON API** — no scraping needed:

```python
import requests

GREENHOUSE_BASE = "https://boards-api.greenhouse.io/v1/boards/{company}/jobs?content=true"

def fetch_greenhouse_jobs(companies: list[str], keywords: list[str]) -> list[dict]:
    jobs = []
    for company in companies:
        url = GREENHOUSE_BASE.format(company=company)
        try:
            data = requests.get(url, timeout=10).json()
            for job in data.get("jobs", []):
                title = job.get("title", "")
                if any(kw.lower() in title.lower() for kw in keywords):
                    jobs.append({
                        "title": title,
                        "company": company.replace("-", " ").title(),
                        "location": job.get("location", {}).get("name", ""),
                        "url": job.get("absolute_url", ""),
                        "source": "Greenhouse",
                    })
        except Exception:
            pass
    return jobs
```

Lever also has a public API — same pattern, replace URL with:
```
https://api.lever.co/v0/postings/{company}?mode=json
```

---

### 2.3 `scrapers/workday.py`
Workday is JS-rendered and requires Playwright:

```python
from playwright.sync_api import sync_playwright

WORKDAY_URL = "https://{subdomain}.wd1.myworkdayjobs.com/en-US/External_Career_Site"

def fetch_workday_jobs(companies: list[tuple], keywords: list[str]) -> list[dict]:
    jobs = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        for company_name, subdomain in companies:
            url = WORKDAY_URL.format(subdomain=subdomain)
            try:
                page.goto(url, timeout=20000)
                page.wait_for_selector("[data-automation-id='jobTitle']", timeout=10000)
                cards = page.query_selector_all("[data-automation-id='jobTitle']")
                for card in cards:
                    title = card.inner_text()
                    if any(kw.lower() in title.lower() for kw in keywords):
                        jobs.append({
                            "title": title,
                            "company": company_name,
                            "location": "",   # enrich in a follow-up step if needed
                            "url": url,
                            "source": "Workday",
                        })
            except Exception:
                pass
        browser.close()
    return jobs
```

> ⚠️ **Cursor Prompt:** "The Workday subdomain URL pattern varies by company. Write a helper that tries both `wd1`, `wd3`, and `wd5` myworkdayjobs subdomains and returns the first one that resolves successfully."

---

### 2.4 `scrapers/niche_boards.py`
Target robotics-specific boards:

- **ROS Jobs Board:** `https://discourse.ros.org/c/jobs/15` (public RSS available)
- **Robotics Tomorrow:** `https://www.roboticstomorrow.com/jobs`
- **IEEE Job Site:** search by keyword
- **Handshake** (if you have a `.edu` email) — manual login required, skip for automation

```python
import feedparser

ROS_RSS = "https://discourse.ros.org/c/jobs/15.rss"

def fetch_ros_jobs(keywords: list[str]) -> list[dict]:
    feed = feedparser.parse(ROS_RSS)
    jobs = []
    for entry in feed.entries:
        title = entry.get("title", "")
        if any(kw.lower() in title.lower() for kw in keywords):
            jobs.append({
                "title": title,
                "company": "See posting",
                "location": "See posting",
                "url": entry.get("link", ""),
                "source": "ROS Discourse",
            })
    return jobs
```

Add `feedparser` to `requirements.txt`.

---

## 🔍 Phase 3 — Filtering & Deduplication

### 3.1 `core/filter.py`
```python
def filter_jobs(jobs: list[dict], keywords: dict) -> list[dict]:
    include_terms = [k.lower() for k in keywords["roles"]]
    exclude_terms = [k.lower() for k in keywords["exclude"]]

    filtered = []
    for job in jobs:
        title_lower = job["title"].lower()
        if any(term in title_lower for term in exclude_terms):
            continue
        if any(term in title_lower for term in include_terms):
            filtered.append(job)
    return filtered
```

### 3.2 `core/deduplicator.py`
Uses a local `seen_jobs.json` file committed to the repo to track jobs already sent. GitHub Actions will commit it back after each run.

```python
import json, hashlib, pathlib

CACHE_FILE = pathlib.Path("data/seen_jobs.json")

def load_seen() -> set:
    if CACHE_FILE.exists():
        return set(json.loads(CACHE_FILE.read_text()))
    return set()

def save_seen(seen: set):
    CACHE_FILE.write_text(json.dumps(list(seen), indent=2))

def deduplicate(jobs: list[dict], seen: set) -> tuple[list[dict], set]:
    new_jobs = []
    for job in jobs:
        job_id = hashlib.md5(job["url"].encode()).hexdigest()
        if job_id not in seen:
            new_jobs.append(job)
            seen.add(job_id)
    return new_jobs, seen
```

---

## 📧 Phase 4 — Email Sender

### 4.1 `templates/digest.html`
A clean HTML email template using Jinja2:

```html
<!DOCTYPE html>
<html>
<head>
  <style>
    body { font-family: Arial, sans-serif; max-width: 700px; margin: auto; color: #222; }
    h1 { color: #1a73e8; }
    .job-card { border: 1px solid #ddd; border-radius: 8px; padding: 12px; margin: 12px 0; }
    .job-title { font-size: 1.1em; font-weight: bold; }
    .job-meta { color: #666; font-size: 0.9em; margin: 4px 0; }
    .source-badge { background: #e8f0fe; color: #1a73e8; padding: 2px 8px; border-radius: 12px; font-size: 0.8em; }
    a { color: #1a73e8; }
  </style>
</head>
<body>
  <h1>🤖 Daily Internship Digest</h1>
  <p>{{ date }} · {{ jobs | length }} new listings</p>
  {% for job in jobs %}
  <div class="job-card">
    <div class="job-title"><a href="{{ job.url }}">{{ job.title }}</a></div>
    <div class="job-meta">🏢 {{ job.company }}</div>
    <div class="job-meta">📍 {{ job.location }}</div>
    <div class="job-meta"><span class="source-badge">{{ job.source }}</span></div>
  </div>
  {% endfor %}
  <p style="color:#aaa; font-size:0.8em;">Unsubscribe by disabling the GitHub Actions workflow.</p>
</body>
</html>
```

### 4.2 `core/email_sender.py`
```python
import smtplib, os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from jinja2 import Environment, FileSystemLoader
from datetime import date

def send_digest(jobs: list[dict], to_email: str, from_email: str):
    app_password = os.environ["GMAIL_APP_PASSWORD"]

    env = Environment(loader=FileSystemLoader("templates"))
    template = env.get_template("digest.html")
    html_body = template.render(jobs=jobs, date=date.today().strftime("%B %d, %Y"))

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🤖 Internship Digest — {len(jobs)} new listings ({date.today()})"
    msg["From"] = from_email
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(from_email, app_password)
        server.sendmail(from_email, to_email, msg.as_string())
```

---

## 🚀 Phase 5 — Entrypoint

### `main.py`
```python
from scrapers.linkedin import fetch_linkedin_jobs
from scrapers.greenhouse import fetch_greenhouse_jobs
from scrapers.workday import fetch_workday_jobs
from scrapers.niche_boards import fetch_ros_jobs
from core.filter import filter_jobs
from core.deduplicator import load_seen, save_seen, deduplicate
from core.email_sender import send_digest
import config

def main():
    all_jobs = []
    kw = config.KEYWORDS["roles"]

    all_jobs += fetch_linkedin_jobs(kw)
    all_jobs += fetch_greenhouse_jobs(config.GREENHOUSE_COMPANIES, kw)
    all_jobs += fetch_workday_jobs(config.WORKDAY_COMPANIES, kw)
    all_jobs += fetch_ros_jobs(kw)

    filtered = filter_jobs(all_jobs, config.KEYWORDS)
    seen = load_seen()
    new_jobs, updated_seen = deduplicate(filtered, seen)

    if new_jobs:
        send_digest(new_jobs, config.TARGET_EMAIL, config.SENDER_EMAIL)
        save_seen(updated_seen)
        print(f"✅ Sent digest with {len(new_jobs)} jobs.")
    else:
        print("No new jobs today. No email sent.")

if __name__ == "__main__":
    main()
```

---

## 🤖 Phase 6 — GitHub Actions Workflow

### `.github/workflows/daily_digest.yml`
```yaml
name: Daily Job Digest

on:
  schedule:
    - cron: "0 13 * * *"   # 6:00 AM Pacific (13:00 UTC) every day
  workflow_dispatch:         # allows manual trigger from GitHub UI

jobs:
  run-digest:
    runs-on: ubuntu-latest
    permissions:
      contents: write        # needed to commit seen_jobs.json back

    steps:
      - name: Checkout repo
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          playwright install chromium
          playwright install-deps chromium

      - name: Run digest
        env:
          GMAIL_APP_PASSWORD: ${{ secrets.GMAIL_APP_PASSWORD }}
        run: python main.py

      - name: Commit updated seen_jobs.json
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add data/seen_jobs.json
          git diff --staged --quiet || git commit -m "chore: update seen jobs cache"
          git push
```

---

## 🔑 Phase 7 — Gmail App Password Setup

1. Go to your Google Account → **Security**
2. Enable **2-Step Verification** if not already on
3. Search for **"App Passwords"** and create one (select "Mail" + "Other")
4. Copy the 16-character password
5. In your GitHub repo → **Settings → Secrets and variables → Actions**
6. Add a new secret: `GMAIL_APP_PASSWORD` = your 16-char password

---

## 🧪 Phase 8 — Local Testing

Before pushing to GitHub, test locally:

```bash
# Create a local .env file (never commit this)
echo "GMAIL_APP_PASSWORD=your_app_password_here" > .env

# Run with dotenv
pip install python-dotenv
python -c "from dotenv import load_dotenv; load_dotenv()"
python main.py
```

Add at the top of `main.py` for local dev:
```python
from dotenv import load_dotenv
load_dotenv()
```

---

## 🛠️ Useful Cursor Prompts to Use While Building

| Step | Prompt |
|------|--------|
| Scrapers | *"Add retry logic with exponential backoff to all HTTP requests in this scraper"* |
| Workday | *"The Workday page isn't loading — try waiting for the network to be idle before scraping"* |
| Dedup | *"Rewrite deduplicator to also track the date a job was first seen and purge entries older than 30 days"* |
| Email | *"Add a plain-text fallback to the MIME email in case HTML rendering fails"* |
| Actions | *"The playwright install-deps step is failing on ubuntu-latest — what's the fix?"* |

---

## ✅ Completion Checklist

- [ ] Repo created and folder structure in place
- [ ] `config.py` filled out with your email and target companies
- [ ] All scrapers implemented and tested individually
- [ ] Filter and deduplicator verified with sample data
- [ ] Email sends successfully in local test
- [ ] `GMAIL_APP_PASSWORD` secret added to GitHub
- [ ] GitHub Actions workflow triggers manually and succeeds
- [ ] Cron schedule confirmed (check timezone — UTC vs Pacific)
- [ ] `seen_jobs.json` committed back after first run
