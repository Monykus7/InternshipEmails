# Job Digest

A daily email digest of SWE, Data Science, and Robotics internship postings scraped from LinkedIn, Greenhouse, Lever, Workday, and ROS Discourse — delivered to your Gmail every morning via GitHub Actions.

---

## Setup

### 1. Configure your email

Edit `config.py` and replace `your@gmail.com` with your Gmail address (or set the `TARGET_EMAIL` / `SENDER_EMAIL` environment variables).

### 2. Create a Gmail App Password

1. Google Account → **Security** → enable **2-Step Verification**
2. Search **"App Passwords"** → create one (Mail / Other)
3. Copy the 16-character password

### 3. Add the secret to GitHub

In your repo: **Settings → Secrets and variables → Actions → New repository secret**

| Name | Value |
|---|---|
| `GMAIL_APP_PASSWORD` | your 16-char app password |

### 4. Install locally (for testing)

```bash
pip install -r requirements.txt
playwright install chromium
```

Create a `.env` file (never commit this):

```
GMAIL_APP_PASSWORD=your_app_password_here
```

Run:

```bash
python main.py
```

---

## Customisation

| File | What to change |
|---|---|
| `config.py` | Email addresses, role keywords, company lists |
| `scrapers/greenhouse.py` | Add/remove Greenhouse or Lever companies |
| `scrapers/workday.py` | Add/remove Workday companies & subdomains |
| `scrapers/niche_boards.py` | Add new RSS feeds or scrapers |
| `.github/workflows/daily_digest.yml` | Change the cron schedule |

---

## Project structure

```
.
├── .github/workflows/daily_digest.yml   # Scheduled GitHub Action
├── scrapers/
│   ├── linkedin.py        # Public job search URL
│   ├── greenhouse.py      # Greenhouse + Lever JSON APIs
│   ├── workday.py         # Playwright (JS-rendered)
│   └── niche_boards.py    # ROS Discourse RSS
├── core/
│   ├── filter.py          # Keyword include/exclude
│   ├── deduplicator.py    # JSON-backed seen-jobs cache
│   └── email_sender.py    # Gmail SMTP + Jinja2 template
├── templates/digest.html  # HTML email template
├── data/seen_jobs.json    # Auto-updated by GitHub Actions
├── config.py
└── main.py
```

---

## Completion checklist

- [ ] `config.py` updated with your Gmail address
- [ ] All scrapers tested individually
- [ ] Local test email received successfully
- [ ] `GMAIL_APP_PASSWORD` secret added to GitHub
- [ ] Workflow triggered manually and succeeded
- [ ] Cron schedule confirmed (13:00 UTC = 6:00 AM Pacific)
