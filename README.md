# Summer 2027 Internship Digest

A daily email digest of **Summer 2027 SWE, ML, Data Science, and Robotics internships** — scraped from the [SimplifyJobs community list](https://github.com/SimplifyJobs/Summer2027-Internships), LinkedIn, Greenhouse, Lever, Workday, and ROS Discourse, then delivered to your Gmail every morning at **6 AM Pacific** via GitHub Actions.

Each digest contains **up to 20 jobs, one per company**, ranked by relevance to a junior CS student.

---

## Project Structure

```
InternshipEmails/
├── .github/
│   └── workflows/
│       └── daily_digest.yml      # GitHub Actions cron (6 AM Pacific daily)
├── scrapers/
│   ├── simplify_jobs.py          # SimplifyJobs/Pitt CSC 2027 GitHub list ← primary source
│   ├── linkedin.py               # LinkedIn public job search
│   ├── greenhouse.py             # Greenhouse + Lever JSON APIs
│   ├── workday.py                # Workday (Playwright headless browser)
│   └── niche_boards.py           # ROS Discourse RSS feed
├── core/
│   ├── filter.py                 # Keyword filter + company-level selection
│   ├── deduplicator.py           # JSON-backed seen-jobs cache (30-day TTL)
│   └── email_sender.py           # Gmail SMTP sender with HTML + plain-text
├── templates/
│   └── digest.html               # Jinja2 HTML email template
├── data/
│   └── seen_jobs.json            # Persisted job cache — auto-committed by CI
├── config.py                     # All settings: email, keywords, companies
├── main.py                       # Orchestrator entrypoint
├── requirements.txt
└── .env                          # Local secrets — never commit this
```

---

## One-Time Setup

### Step 1 — Clone the repo

```bash
git clone https://github.com/<your-username>/InternshipEmails.git
cd InternshipEmails
```

### Step 2 — Create a virtual environment

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

### Step 3 — Install dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

### Step 4 — Configure your email

Open `config.py` and set your Gmail address on lines 4–5:

```python
TARGET_EMAIL = os.getenv("TARGET_EMAIL", "you@gmail.com")
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "you@gmail.com")
```

Both should be the **same Gmail account** that owns the App Password.

### Step 5 — Create a Gmail App Password

> Regular Gmail passwords won't work. You need an App Password.

1. Go to [myaccount.google.com/security](https://myaccount.google.com/security)
2. Enable **2-Step Verification** if not already on
3. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
4. Create a new App Password → name it anything (e.g. "Job Digest")
5. Copy the **16-character** code (no spaces)

### Step 6 — Create your local `.env` file

```bash
# In the project root — never commit this file
echo GMAIL_APP_PASSWORD=abcdabcdabcdabcd > .env
```

Replace `abcdabcdabcdabcd` with your actual 16-character App Password (no spaces).

### Step 7 — Run a local test

```bash
python main.py
```

Expected output:

```
18:20:01 [INFO] __main__: ── Scraping SimplifyJobs 2027 list …
18:20:03 [INFO] scrapers.simplify_jobs: SimplifyJobs → 137 keyword-matching listings
18:20:03 [INFO] __main__: ── Scraping LinkedIn …
...
18:22:15 [INFO] __main__: Total raw results: 750
18:22:15 [INFO] __main__: After keyword + year filter: 140
18:22:15 [INFO] __main__: New (unseen) jobs: 140
18:22:15 [INFO] __main__: Selected 20 jobs across 20 unique companies for digest.
18:22:16 [INFO] core.email_sender: Digest sent to you@gmail.com (20 jobs).
```

Check your inbox — you should receive the digest within a few seconds.

> **Runtime:** ~3–4 minutes total. LinkedIn takes the longest (polite delays between keyword searches). Workday uses a real browser (Playwright) and adds another minute.

---

## GitHub Actions Setup (Automated Daily Runs)

Once the local test passes, push to GitHub and configure the secret so it runs automatically every morning.

### Step 1 — Push the repo to GitHub

```bash
git add .
git commit -m "Initial setup"
git push
```

> **Do not commit `.env`** — it is already in `.gitignore`.

### Step 2 — Add the GitHub Actions secret

1. Open your repo on GitHub
2. Go to **Settings → Secrets and variables → Actions**
3. Click **New repository secret**
4. Name: `GMAIL_APP_PASSWORD`
5. Value: your 16-character App Password (no spaces)
6. Click **Add secret**

### Step 3 — Trigger a manual run to verify

1. Go to **Actions** tab in your repo
2. Select **Daily Job Digest**
3. Click **Run workflow → Run workflow**
4. Watch the logs — it should complete and send an email

### Step 4 — Let it run automatically

The workflow is scheduled at `0 13 * * *` UTC = **6:00 AM Pacific (PDT)**.

After each run, GitHub Actions automatically commits an updated `seen_jobs.json` back to the repo so duplicates are never emailed again. You don't need to do anything.

---

## Customisation

### Change target year / season

In `config.py`:

```python
TARGET_YEAR = "2027"
TARGET_SEASON = "summer"
```

### Adjust how many jobs per digest

```python
DIGEST_TARGET_COUNT = 20   # up to this many, one per company
```

### Add / remove role keywords

Edit the `KEYWORDS["roles"]` list in `config.py`. The filter keeps a job only if its title contains **at least one** role keyword. The `"exclude"` list drops jobs whose title contains seniority terms.

### Add more companies

**Greenhouse** (free public API — no key needed):

```bash
# Verify a slug works before adding it to config
curl https://boards-api.greenhouse.io/v1/boards/<slug>/jobs
```

Add the verified slug to `GREENHOUSE_COMPANIES` in `config.py`.

**Lever** (same pattern):

```bash
curl "https://api.lever.co/v0/postings/<slug>?mode=json"
```

**Workday** — add a 3-tuple to `WORKDAY_COMPANIES`:

```python
("Company Name", "workday-subdomain", "Career_Site_Path")
# e.g. the URL https://acme.wd1.myworkdayjobs.com/en-US/Careers
# becomes: ("Acme Corp", "acme", "Careers")
```

### Change the send time

In `.github/workflows/daily_digest.yml`, edit the cron expression:

```yaml
- cron: "0 13 * * *"   # 13:00 UTC = 6:00 AM Pacific
```

Use [crontab.guru](https://crontab.guru) to generate a new expression.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `SMTPAuthenticationError (535)` | Wrong or missing App Password | Re-generate at [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords); paste without spaces |
| `No new listings today` on first run | `seen_jobs.json` already populated from a previous run | Delete `data/seen_jobs.json` content (`{}`) and re-run |
| Workday shows all warnings | Workday is down for maintenance or the `career_site_path` is wrong | Check the company's actual Workday URL and update the 3-tuple in `config.py` |
| LinkedIn returns 0 results | LinkedIn blocked the request | The scraper retries with backoff automatically; try again in a few minutes |
| Fewer than 20 jobs in digest | Not enough new listings matching filters that day | Normal — the list grows as more companies open 2027 roles in Aug–Sep |

---

## Completion Checklist

- [x] Repo cloned and virtual environment created
- [x] `pip install -r requirements.txt` and `playwright install chromium` run
- [x] Gmail address set in `config.py`
- [x] `.env` file created with `GMAIL_APP_PASSWORD`
- [x] Local `python main.py` test succeeded and email received
- [ ] Repo pushed to GitHub
- [ ] `GMAIL_APP_PASSWORD` secret added to GitHub Actions
- [ ] Manual workflow trigger succeeded
- [ ] Cron confirmed running at 6 AM Pacific
