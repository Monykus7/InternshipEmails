import os

# ── Email ─────────────────────────────────────────────────────────────────────
TARGET_EMAIL = os.getenv("TARGET_EMAIL", "adityamahesh16@gmail.com")
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "adityamahesh16@gmail.com")
# GMAIL_APP_PASSWORD is loaded from env (GitHub Actions secret / local .env)

# ── Cohort targeting ──────────────────────────────────────────────────────────
# Jobs explicitly naming a *different* year are dropped.
# Jobs with no year in the title are always kept.
TARGET_YEAR = "2027"
TARGET_SEASON = "summer"

# ── Digest target ─────────────────────────────────────────────────────────────
# Aim for this many jobs per email, one per company.
DIGEST_TARGET_COUNT = 20

# ── Keywords ──────────────────────────────────────────────────────────────────
KEYWORDS = {
    "roles": [
        # Core SWE
        "software engineer intern",
        "software engineering intern",
        "software developer intern",
        "software development engineer intern",
        "swe intern",
        "computer science intern",
        # Backend / Frontend / Full-stack
        "backend engineer intern",
        "backend software engineer intern",
        "frontend engineer intern",
        "full stack engineer intern",
        "fullstack engineer intern",
        # ML / AI / Data
        "machine learning intern",
        "ml intern",
        "ai intern",
        "applied ml intern",
        "deep learning intern",
        "computer vision intern",
        "nlp intern",
        "data science intern",
        "data scientist intern",
        "data engineer intern",
        # Robotics / Autonomy
        "robotics software intern",
        "robotics engineer intern",
        "robot perception intern",
        "autonomy intern",
        "perception engineer intern",
        "embedded software intern",
        # Research
        "research engineer intern",
        "research intern",
    ],
    # Titles containing any of these are dropped (seniority / non-student roles)
    "exclude": [
        "senior", "staff", "principal", "lead", "manager", "director",
        "phd", "doctoral", "postdoc", "post-doc",
        "vice president", "vp ", " vp",
    ],
}

# ── Source toggles ────────────────────────────────────────────────────────────
SOURCES = {
    "simplify_jobs": True,   # SimplifyJobs Summer 2027 GitHub list (best source)
    "linkedin": True,
    "greenhouse": True,
    "lever": True,
    "workday": True,
    "niche_boards": True,
}

# ── Company lists ─────────────────────────────────────────────────────────────
# All slugs below verified via the Greenhouse public API (Aug 2026).
# Companies with 0 current intern postings are still included — they will post
# 2027 summer roles as the recruiting cycle opens (typically Sep–Dec).
GREENHOUSE_COMPANIES = [
    # ── AI / ML / LLM labs ────────────────────────────────────────────────────
    "anthropic",        # 6 intern postings
    "togetherai",       # 3 intern postings
    "scaleai",          # 3 intern postings
    "coreweave",        # GPU cloud — SWE intern roles
    "motional",         # Autonomous vehicle AI (Hyundai/Aptiv JV)
    "stabilityai",      # Stable Diffusion

    # ── Robotics / Autonomy ───────────────────────────────────────────────────
    "waymo",            # 7 intern postings
    "nuro",             # 1 intern posting
    "apptronik",        # 1 intern posting
    "kodiak",           # Autonomous trucking

    # ── Cybersecurity ─────────────────────────────────────────────────────────
    "cloudflare",       # 16 intern postings — great SWE internship program

    # ── Fintech / Payments ────────────────────────────────────────────────────
    "stripe",           # 11 intern postings
    "coinbase",         # 6 intern postings
    "robinhood",        # 9 intern postings
    "affirm",           # 6 intern postings
    "adyen",            # 4 intern postings
    "brex",             # 1 intern posting
    "mercury",          # 1 intern posting
    "chime",
    "marqeta",
    "ripple",

    # ── Developer tools / Infra ───────────────────────────────────────────────
    "databricks",       # 10 intern postings
    "gitlab",           # 3 intern postings
    "twilio",           # 3 intern postings
    "vercel",           # 1 intern posting
    "samsara",          # 2 intern postings — IoT/fleet software
    "hashicorp",
    "amplitude",
    "mixpanel",
    "pagerduty",
    "webflow",

    # ── Consumer / Social ─────────────────────────────────────────────────────
    "airbnb",           # 2 intern postings
    "lyft",             # 2 intern postings
    "reddit",           # 1 intern posting
    "pinterest",        # 1 intern posting
    "discord",
    "instacart",        # 1 intern posting
    "faire",            # 1 intern posting — wholesale marketplace
    "duolingo",
    "coursera",

    # ── Gaming / Creative ─────────────────────────────────────────────────────
    "epicgames",        # 3 intern postings
    "roblox",           # 1 intern posting
    "insomniac",        # (PlayStation Studios)
    "bungie",

    # ── Design / Productivity ────────────────────────────────────────────────
    "figma",            # 2 intern postings
    "airtable",
    "asana",
    "notion",
    "retool",

    # ── Biotech / MedTech (software-heavy roles) ──────────────────────────────
    "relativity",       # 1 intern posting
    "benchling",        # Lab software platform
    "recursion",        # Biotech + ML

    # ── Other tech ────────────────────────────────────────────────────────────
    "toast",            # 6 intern postings — restaurant SaaS
    "gusto",
    "carta",
    "lattice",
    "verkada",          # Physical security + software
]

# Slugs verified against https://api.lever.co/v0/postings/{slug}?mode=json
LEVER_COMPANIES = [
    "zoox",
]

WORKDAY_COMPANIES = [
    # (display_name, workday_subdomain, career_site_path)
    # All entries verified reachable via the Workday REST search API (Aug 2026).
    # Removed: Northrop Grumman, Lockheed Martin, Raytheon (require security clearance)
    ("Boston Dynamics",  "bostondynamics", "Boston_Dynamics"),
    ("Stryker",          "stryker",        "StrykerCareers"),
    ("Medtronic",        "medtronic",      "MedtronicCareers"),
    ("Applied Materials","amat",           "External"),
    ("CrowdStrike",      "crowdstrike",    "crowdstrikecareers"),
    ("Workday",          "workday",        "Workday"),
]

NICHE_BOARDS = [
    "https://www.robotics-worldwide.org/jobs/",
]
