"""
config.py — Job Feed v3 Configuration
All constants, company lists, role taxonomy, and filter rules.
"""

# ─── TARGET LOCATIONS ────────────────────────────────────────────────────────
US_LOCATIONS = [
    "san francisco", "bay area", "palo alto", "menlo park",
    "mountain view", "santa clara", "sunnyvale", "san jose", "oakland",
    "california", "seattle", "bellevue", "redmond",
    "new york", "nyc", "chicago", "boston", "cambridge",
    "austin", "united states", "u.s.", "usa", "remote",
]
# State abbreviation patterns — require word boundaries
US_STATE_ABBREVS = [
    "ca", "ny", "il", "ma", "tx", "wa", "co", "ga", "nc", "va",
    "pa", "nj", "ct", "or", "az", "mn", "oh", "mi", "fl", "md",
]

INTL_EXCLUDE = [
    "india", "bengaluru", "bangalore", "hyderabad", "pune", "delhi",
    "singapore", "london", "dublin", "amsterdam", "berlin", "paris",
    "barcelona", "toronto", "vancouver", "sydney", "tokyo",
    "united kingdom", "emea", "apac", "latam", "canada", "australia",
    "brazil", "mexico", "germany", "france", "netherlands",
    "u.k.", "uk,",
]

# ─── ROLE TAXONOMY ────────────────────────────────────────────────────────────

# TITLE_BLACKLIST runs BEFORE any category matching — if any of these appear
# in the title (case-insensitive, word-boundary matched), return None immediately.
# NOTE: Do NOT add "customer success" here — it is now a target category.
TITLE_BLACKLIST = [
    # ── Engineering ─────────────────────────────────────────────────────────
    "software engineer", "data engineer", "ml engineer",
    "machine learning engineer", "devops", "sre", "site reliability",
    "backend engineer", "frontend engineer", "fullstack", "full stack",
    "mobile engineer", "android engineer", "ios engineer",
    "embedded engineer", "platform engineer", "infrastructure engineer",
    "network engineer", "systems engineer", "cloud engineer",
    "security engineer", "solutions engineer",
    # ── Support / Service ────────────────────────────────────────────────────
    "support engineer", "technical support", "customer support",
    "customer service", "customer operations",
    # ── QA / Test ────────────────────────────────────────────────────────────
    "qa engineer", "test engineer", "sdet",
    # ── Data Science / Research ──────────────────────────────────────────────
    "data scientist", "research scientist", "applied scientist",
    "research engineer",
    # ── Design / UX ─────────────────────────────────────────────────────────
    "designer", "ux researcher", "ux designer", "product designer",
    # ── Pure Sales ──────────────────────────────────────────────────────────
    "account executive", "sales engineer", "sales representative",
    "sales development", "business development representative",
    # ── Marketing (non-strategic) ────────────────────────────────────────────
    "content manager", "brand manager", "social media manager",
    "demand generation manager", "email marketing",
    # ── HR / Recruiting ─────────────────────────────────────────────────────
    "recruiter", "hr manager", "people operations", "talent acquisition",
    # ── Legal / Compliance ───────────────────────────────────────────────────
    "legal counsel", "compliance officer",
    # ── Finance (execution, not strategic) ──────────────────────────────────
    "accountant", "bookkeeper", "payroll",
]

# Each entry uses tuples: (pattern, _unused_flag)
# Category order matters — more specific categories come first.
# AI/ML PM before generic PM; Solutions/Pre-Sales before generic Consulting.
ROLE_CATEGORIES = {
    # ── 1. AI/ML Product Manager ────────────────────────────────────────────
    "AI/ML Product Manager": [
        (r"ai product manager", False),
        (r"ml product manager", False),
        (r"ai/ml product manager", False),
        (r"product manager,?\s+ai\b", False),
        (r"product manager,?\s+ml\b", False),
        (r"product manager,?\s+machine learning", False),
        (r"product manager,?\s+artificial intelligence", False),
        (r"product manager\s+-\s+ai\b", False),
        (r"product manager\s+-\s+ml\b", False),
        (r"product manager,?\s+generative ai", False),
        (r"product manager,?\s+llm", False),
        (r"product manager,?\s+foundation model", False),
        (r"product manager,?\s+data\b", False),
        (r"product manager,?\s+analytics", False),
    ],
    # ── 2. Product Manager ──────────────────────────────────────────────────
    "Product Manager": [
        (r"product manager", False),
        (r"product management", False),
        (r"\bsenior pm\b", False),
        (r"\bsr\.?\s*pm\b", False),
        (r"\bgroup pm\b", False),
        (r"\bstaff pm\b", False),
        (r"product lead", False),
        (r"product owner", False),
        (r"forward.?deployed pm\b", False),
        (r"forward.?deployed product manager", False),
        (r"technical product manager", False),
        (r"\bassociate product manager\b", False),   # APM is a target role
        (r"\bapm\b", False),                         # APM abbreviation
        (r"\bgroup pm\b", False),
    ],
    # ── 3. Product Marketing ────────────────────────────────────────────────
    "Product Marketing": [
        (r"product marketing manager", False),
        (r"product marketing lead", False),
        (r"product marketing director", False),
        (r"\bpmm\b", False),
        (r"product go.?to.?market", False),
        (r"product launch manager", False),
        (r"product growth manager", False),
        (r"solutions marketing", False),
        (r"technical marketing manager", False),
    ],
    # ── 4. Technical Program Manager ────────────────────────────────────────
    "Technical Program Manager": [
        (r"technical program manager", False),
        (r"engineering program manager", False),
        (r"\btpm\b", False),
        (r"program manager", False),
        (r"program management", False),
        (r"delivery manager", False),
        (r"release manager", False),
        (r"it program manager", False),
    ],
    # ── 5. Strategy & Operations ─────────────────────────────────────────────
    "Strategy & Operations": [
        (r"strategy and operations", False),
        (r"strategy & operations", False),
        (r"strategy,\s*operations", False),
        (r"\bbizops\b", False),
        (r"\bbiz ops\b", False),
        (r"business operations", False),
        (r"\bbusiness ops\b", False),
        (r"strategic operations", False),
        (r"growth operations", False),
        (r"revenue operations", False),
        (r"\brevops\b", False),
        (r"chief of staff", False),
        (r"go.?to.?market\s+manager", False),
        (r"go.?to.?market\s+lead", False),
        (r"\bgtm strategy\b", False),
        (r"\bgtm operations\b", False),
        (r"market operations", False),
        (r"corporate strategy", False),
        (r"commercial operations", False),
        (r"sales operations", False),
        (r"\bsales ops\b", False),
    ],
    # ── 6. Finance & Strategy / FP&A ─────────────────────────────────────────
    "Finance & Strategy / FP&A": [
        (r"\bfp&a\b", False),
        (r"financial planning and analysis", False),
        (r"financial planning & analysis", False),
        (r"strategic finance", False),
        (r"finance manager", False),
        (r"finance analyst", False),
        (r"financial analyst", False),
        (r"senior finance", False),
        (r"\bsr\.?\s*finance\b", False),
        (r"corporate finance", False),
        (r"business finance", False),
        (r"finance business partner", False),
        (r"investment analyst", False),
        (r"treasury analyst", False),
        (r"treasury manager", False),
        (r"finance lead", False),
        (r"finance associate", False),
    ],
    # ── 7. Consulting ────────────────────────────────────────────────────────
    "Consulting": [
        # Management / Generalist (most common, listed first)
        (r"management consultant", False),
        (r"strategy consultant", False),
        (r"senior consultant", False),
        (r"associate consultant", False),
        (r"business consultant", False),
        (r"principal consultant", False),
        (r"consulting analyst", False),
        (r"consulting manager", False),
        (r"advisory manager", False),
        (r"advisory analyst", False),
        (r"advisory consultant", False),
        (r"engagement manager", False),
        (r"case team leader", False),
        (r"\bconsultant,", False),           # "Consultant, Strategy" etc.
        # Implementation / Technology
        (r"implementation consultant", False),
        (r"technology consultant", False),
        (r"\berp consultant\b", False),
        (r"\bsap consultant\b", False),
        (r"technology implementation", False),
        (r"digital implementation", False),
        (r"technical consultant", False),
        (r"integration consultant", False),
        (r"platform consultant", False),
        (r"cloud consultant", False),
        (r"systems consultant", False),
        # AI / Strategy / Transformation
        (r"ai strategy consultant", False),
        (r"\bai consultant\b", False),
        (r"ai transformation", False),
        (r"digital transformation consultant", False),
        (r"digital strategy consultant", False),
        (r"transformation consultant", False),
        (r"digital consultant", False),
        (r"innovation consultant", False),
        (r"analytics consultant", False),
        (r"data strategy consultant", False),
        # Product / Operations
        (r"product consultant", False),
        (r"product strategy consultant", False),
        (r"growth consultant", False),
        (r"commercial consultant", False),
        (r"operations consultant", False),
        (r"process consultant", False),
        (r"\bconsulting\b", False),         # "Director, Consulting" etc.
    ],
    # ── 8. Customer Success ──────────────────────────────────────────────────
    "Customer Success": [
        (r"customer success manager", False),
        (r"\bcsm\b", False),
        (r"customer success lead", False),
        (r"customer success director", False),
        (r"customer success specialist", False),
        (r"client success manager", False),
        (r"account success manager", False),
        (r"customer outcomes manager", False),
        (r"customer growth manager", False),
    ],
    # ── 9. Solutions / Pre-Sales ─────────────────────────────────────────────
    "Solutions / Pre-Sales": [
        (r"solutions consultant", False),
        (r"solutions architect", False),
        (r"pre.?sales consultant", False),
        (r"pre.?sales engineer", False),
        (r"sales consultant", False),
        (r"value engineer", False),
        (r"value consultant", False),
        (r"sales architect", False),
        (r"technical sales", False),
    ],
}

# ─── SENIORITY FILTERS ──────────────────────────────────────────────────────

# Always excluded regardless of category (C-suite, EVP/SVP, VP)
SENIOR_EXCLUDE_ALWAYS = [
    r"vice president",
    r"\bvp[,\s/]",
    r"\bvp$",
    r"^vp\b",
    r"\bsvp\b",
    r"\bevp\b",
    r"\bhead of\b",
    r"\bchief\s(?!of\s+staff)",    # Chief X but NOT "Chief of Staff"
    r"managing director",
    r"general manager",
    r"\bc-suite\b",
    r"\bfellow\b",
]

# Excluded for non-Consulting categories only
# (Directors, Principals, Partners are legitimate targets in consulting)
SENIOR_EXCLUDE_NON_CONSULTING = [
    r"^staff\b",            # "Staff Product Manager" at start (not "chief of staff to...")
    r"\bprincipal\b",
    r"\bdirector\b",
    r"\bpartner\b",
]

# Kept for backwards compat — filters.py uses SENIOR_EXCLUDE_PATTERNS
# for the non-Consulting check
SENIOR_EXCLUDE_PATTERNS = SENIOR_EXCLUDE_ALWAYS + SENIOR_EXCLUDE_NON_CONSULTING

# Patterns that indicate too junior (APM is intentionally NOT here)
JUNIOR_EXCLUDE_PATTERNS = [
    r"\bintern\b",
    r"\binternship\b",
    r"\bco-op\b",
    r"\bco op\b",
    r"entry.?level",
    r"\bjunior\b",
    r"\bjr\.\s",
    r"\bnew grad\b",
    r"new graduate",
    r"\bapprentice\b",
    r"\brotational\b",
    r"early career",
    r"early talent",
]

# Program manager titles that match non-target program domains.
# If a title matches a Program Manager category AND contains any of these
# words, reject it (e.g. "Loyalty Program Manager", "Benefits Program Manager").
PROGRAM_MANAGER_DISQUALIFIERS = [
    "loyalty", "affiliate", "rewards", "referral",
    "benefits", "compensation", "facilities", "office",
    "events", "wellness", "perks", "volunteer",
    "hr", "payroll", "vendor", "compliance",
    "community", "social", "brand ambassador",
]

XP_DISQUALIFY = [
    "10+ years", "10 or more years", "10+ yrs",
    "12+ years", "12 or more years",
    "15+ years", "15 or more years",
    "10 years of experience", "12 years of experience",
]

# ─── STALE JOB FILTER ──────────────────────────────────────────────────────
MAX_JOB_AGE_DAYS = 30  # Filter at fetch time

# ─── VISA SPONSORS ────────────────────────────────────────────────────────────
VISA_SPONSORS = {
    # Fintech
    "stripe", "brex", "ramp", "plaid", "chime", "affirm", "marqeta", "coinbase",
    "robinhood", "carta", "mercury", "moderntreasury", "klarna", "adyen", "navan",
    "airwallex", "nium", "sofi", "upgrade", "betterment", "wealthfront", "lithic",
    "parafin", "jeeves", "oscar", "cityblock", "flatiron", "veeva", "transcarent",
    "truepill", "hims", "ro", "inovalon", "cedar", "waystar", "medallion",
    "figma", "notion", "airtable", "retool", "lattice", "rippling", "deel",
    "remote", "gusto", "databricks", "snowflake", "confluent", "datadog",
    "mixpanel", "amplitude", "braze", "klaviyo", "intercom", "gong",
    "productboard", "pendo", "launchdarkly", "statsig", "miro", "loom",
    "asana", "coda", "glean", "gleanwork", "iterable", "linear", "zapier",
    "vercel", "anthropic", "scaleai", "cohere", "huggingface", "openai",
    "perplexity", "cursor", "replit", "runway", "runwayml", "writer", "harvey",
    "cloudflare", "twilio", "okta", "samsara", "verkada", "benchling",
    "google", "amazon", "microsoft", "apple", "meta", "uber", "lyft", "airbnb",
    "doordash", "pinterest", "linkedin", "palantir", "salesforce", "workday",
    "servicenow", "oracle", "intuit", "adobe", "visa", "freshworks", "docusign",
    "elevenlabs", "sierra", "zip", "clerk", "stedi",
    # Big Tech (new)
    "nvidia", "amd", "qualcomm", "intel", "cisco", "dell", "hp", "ibm", "sap",
    "block", "square", "paypal", "ebay", "snap", "reddit", "discord", "spotify",
    "netflix", "tesla",
    # Enterprise SaaS (new)
    "zscaler", "crowdstrike", "paloaltonetworks", "fortinet", "elastic",
    "sumologic", "pagerduty", "harness", "uipath", "celonis",
    # AI/ML (new)
    "labelbox", "anyscale", "ai21labs", "groq",
    # Healthcare (new)
    "tempus", "omadahealth", "swordhealth", "hingehealth", "springhealth",
    "lyrahealth", "devotedhealth", "cloverhealth",
    # Consulting (new)
    "mckinsey", "bcg", "bain", "deloitte", "accenture", "kearney",
    "oliverwyman", "alixpartners", "huron", "westmonroe", "slalom",
    "thoughtworks", "capgemini", "cognizant", "infosys", "wipro", "tcs",
    # Supply chain
    "flexport", "fourkites", "project44", "shipbob",
}

# ─── ATS COMPANY LISTS ────────────────────────────────────────────────────────

GREENHOUSE_SLUGS = [
    # Fintech
    "stripe", "brex", "plaid", "chime", "affirm", "marqeta", "coinbase", "robinhood",
    "carta", "mercury", "moderntreasury", "klarna", "airwallex", "nium", "sofi",
    "upgrade", "betterment", "wealthfront", "lithic", "navan", "zip", "slope", "unit",
    "synctera", "capchase", "parafin", "jeeves", "adyen",
    "toast", "bill", "payoneer", "flywire", "greenlight", "moneylion",
    "current", "step", "varo", "crossriver",
    # Healthtech
    "oscar", "cityblock", "flatiron", "veeva", "transcarent", "truepill", "hims",
    "ro", "alto", "wheel", "inovalon", "cedar", "waystar", "cohereahealth",
    "garnerhealth", "medallion", "ribbonhealth", "turquoisehealth", "stedi",
    "tempus", "omadahealth", "swordhealth", "hingehealth", "springhealth",
    "lyrahealth", "headspace", "calm", "cerebral", "colorhealth",
    # Enterprise SaaS
    "notion", "airtable", "retool", "lattice", "rippling", "deel", "remote",
    "gusto", "figma", "databricks", "snowflake", "confluent", "datadog", "mixpanel",
    "amplitude", "braze", "klaviyo", "intercom", "gong", "salesloft", "outreach",
    "productboard", "pendo", "launchdarkly", "statsig", "miro", "loom", "asana",
    "mondaydotcom", "coda", "gleanwork", "fullstory", "heap", "iterable", "zapier",
    "linear", "contentful", "optimizely", "bloomreach", "algolia", "segment",
    "contentstack", "celonis", "uipath", "automationanywhere", "pegasystems",
    # AI / ML
    "anthropic", "scaleai", "cohere", "huggingface", "weightsandbiases",
    "togetherai", "writer", "runwayml", "perplexity", "harvey", "evisort",
    "ironclad", "elevenlabs", "labelbox", "snorkel", "tecton", "modal", "baseten",
    "anyscale", "mosaicml", "groq", "cerebras", "sambanova", "ai21labs",
    # Infra / Security
    "palantir", "cloudflare", "twilio", "okta", "hashicorp", "grafana", "samsara",
    "verkada", "benchling", "github", "vercel", "planetscale",
    "zscaler", "crowdstrike", "paloaltonetworks", "fortinet", "elastic",
    "sumologic", "pagerduty", "harness",
    # Big tech
    "google", "amazon", "microsoft", "apple", "meta", "uber", "lyft", "airbnb",
    "doordash", "pinterest", "linkedin", "salesforce", "intuit", "adobe", "workday",
    "servicenow", "oracle", "shopify", "atlassian", "zendesk", "hubspot", "freshworks",
    "nvidia", "amd", "qualcomm", "intel", "cisco", "dell", "hp", "ibm",
    "block", "paypal", "ebay", "snap", "reddit", "discord", "twitch", "spotify",
    "netflix", "tesla", "rivian", "lucid",
    # Supply chain / logistics
    "flexport", "fourkites", "project44", "shippo", "shipbob",
    # Consulting (Greenhouse)
    "slalom", "thoughtworks",
]

LEVER_SLUGS = [
    "palantir", "spotify", "outreach", "clari", "newrelic",
    "mistral", "stabilitiai", "characterai", "inflection", "adept",
    "westmonroe", "huron", "simonkucher",
]

ASHBY_SLUGS = [
    # Fintech
    "ramp", "mercury", "moderntreasury", "jeeves", "parafin", "arc", "unit",
    "lithic", "synctera", "capchase", "zip", "slope", "navan",
    "marqeta", "gohenry",
    # AI / ML
    "openai", "perplexity", "cursor", "replit", "runway", "elevenlabs", "harvey",
    "evisort", "ironclad", "glean", "sierra", "cohere", "writer", "synthesia",
    "mistral", "stabilitiai", "adept", "xai",
    # Dev tools / Infra
    "linear", "vercel", "retool", "loom", "coda", "raycast", "descript", "workos",
    "clerk", "planetscale", "neon", "supabase", "resend", "loop", "superhuman",
    "craft", "grammarly",
    # Healthtech
    "transcarent", "cityblock", "garnerhealth", "ribbonhealth",
    "turquoisehealth", "stedi", "wheel", "swordhealth", "hingehealth",
    "springhealth", "lyrahealth",
    # Consulting
    "alixpartners",
]

SMARTRECRUITERS_SLUGS = [
    "servicenow", "visa", "freshworks", "palantir", "docusign",
    "mckinsey", "bcg", "bain", "kearney", "oliverwyman", "lek",
    "capgemini", "cognizant", "infosys", "wipro", "tcs",
]

# ─── WORKDAY COMPANIES ───────────────────────────────────────────────────────
# Format: (company_name, workday_tenant_url_slug, site_name)
WORKDAY_COMPANIES = [
    ("Visa", "visa", "Visa_Careers"),
    ("Netflix", "netflix", "External"),
    ("Capital One", "capitalone", "Capital_One"),
    ("JPMorgan", "jpmorgan", "careers"),
    ("Goldman Sachs", "gs", "GS_Careers"),
    ("Deloitte", "deloitte", "Deloitte_Careers"),
    ("McKinsey", "mckinsey", "careers"),
    ("BCG", "bcg", "BCG_Careers"),
    ("Accenture", "accenture", "AccentureCareers"),
    ("IBM", "ibm", "careers"),
    ("SAP", "sap", "SAP_Careers"),
    ("Cisco", "cisco", "Cisco_Careers"),
    ("Intel", "intel", "Intel_Careers"),
    ("PayPal", "paypal", "paypalcareers"),
    ("Salesforce", "salesforce", "careers"),
    ("Adobe", "adobe", "AdobeCareers"),
    ("Workday", "workday", "workdaycareers"),
    ("Oracle", "oracle", "OracleCareers"),
    ("Intuit", "intuit", "careers"),
    ("ServiceNow", "servicenow", "External"),
    ("Cognizant", "cognizant", "CognizantCareers"),
    ("Infosys", "infosys", "InfysysCareers"),
    ("Wipro", "wipro", "wiprocareer"),
    ("Capgemini", "capgemini", "Capgemini_Careers"),
    ("Alignment Healthcare", "alignmenthealthcare", "careers"),
    ("Clover Health", "cloverhealth", "CareersClover"),
    ("Devoted Health", "devotedhealth", "DevotedCareers"),
    ("UiPath", "uipath", "careers"),
    ("PagerDuty", "pagerduty", "careers"),
    ("Elastic", "elastic", "ElasticCareers"),
    ("CrowdStrike", "crowdstrike", "careers"),
    ("Palo Alto Networks", "paloaltonetworks", "careers"),
    ("Zscaler", "zscaler", "External"),
]

# ─── SCORING ──────────────────────────────────────────────────────────────────
# Weights for composite JD match score (0-100)
SCORE_WEIGHTS = {
    "keyword_match": 0.40,   # % of relevant keywords found in JD
    "category_fit": 0.20,    # How well title matches target categories
    "visa_sponsor": 0.10,    # Known sponsor = bonus
    "freshness": 0.10,       # Newer = higher score
    "mba_bonus": 15,         # flat bonus points (not a weight)
}

# ─── APPLICATION TRACKING STATUSES ────────────────────────────────────────────
APP_STATUSES = [
    "new",            # Just found
    "saved",          # Bookmarked for review
    "applying",       # In progress
    "applied",        # Submitted
    "interviewing",   # In interview process
    "offer",          # Received offer
    "rejected",       # Rejected / closed
    "withdrawn",      # User withdrew
    "expired",        # Listing removed
]

# ─── PATHS ────────────────────────────────────────────────────────────────────
import os
FEED_DIR = os.path.expanduser("~/job_feed")
OUTPUT_DIR = os.path.join(FEED_DIR, "daily_outputs")
DB_PATH = os.path.join(FEED_DIR, "job_feed.db")
KEYWORDS_PATH = os.path.join(FEED_DIR, "jd_keywords.json")
LOG_FILE = os.path.join(FEED_DIR, "feed.log")
