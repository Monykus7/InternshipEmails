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
# Slugs verified against https://boards-api.greenhouse.io/v1/boards/{slug}/jobs
GREENHOUSE_COMPANIES = [
    # Robotics / Autonomy / AI
    "waymo",
    "scaleai",
    "nuro",
    "kodiak",
    "apptronik",
    "togetherai",
    # Finance / Fintech (strong SWE intern programs)
    "robinhood",
    "brex",
    "mercury",
    # General tech with good intern programs
    "databricks",
    "figma",
    "reddit",
    "pinterest",
    "carta",
    "gusto",
]

# Slugs verified against https://api.lever.co/v0/postings/{slug}?mode=json
LEVER_COMPANIES = [
    "zoox",
]

WORKDAY_COMPANIES = [
    # (display_name, workday_subdomain, career_site_path)
    # https://{subdomain}.wd1.myworkdayjobs.com/en-US/{career_site_path}
    ("Boston Dynamics",    "bostondynamics",    "Boston_Dynamics"),
    ("Intuitive Surgical", "intuitivesurgical", "Careers"),
    ("Northrop Grumman",   "northropgrumman",   "Northrop_Grumman_External_Site"),
    ("Lockheed Martin",    "lmco",              "External"),
    ("Raytheon",           "rtx",               "RTXCareers"),
]

NICHE_BOARDS = [
    "https://www.robotics-worldwide.org/jobs/",
]
