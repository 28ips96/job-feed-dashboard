"""
filters.py — Job Feed v3 Filtering Engine
Proper word-boundary matching, location detection, seniority filters.
"""
import re
from datetime import datetime
from config import (
    US_LOCATIONS, US_STATE_ABBREVS, INTL_EXCLUDE,
    TITLE_BLACKLIST, ROLE_CATEGORIES,
    SENIOR_EXCLUDE_ALWAYS, SENIOR_EXCLUDE_NON_CONSULTING,
    JUNIOR_EXCLUDE_PATTERNS, PROGRAM_MANAGER_DISQUALIFIERS,
    XP_DISQUALIFY, VISA_SPONSORS, MAX_JOB_AGE_DAYS,
)


def norm(text: str) -> str:
    return text.lower().strip() if text else ""


def _match(pattern: str, text: str) -> bool:
    """Regex search (pattern already contains any needed anchors/boundaries)."""
    return bool(re.search(pattern, text, re.IGNORECASE))


# ─── LOCATION ─────────────────────────────────────────────────────────────────

def location_ok(loc: str) -> bool:
    """Check if location is US-based. Returns False for international."""
    l = norm(loc)
    if not l:
        return False

    # Reject international locations first
    for excl in INTL_EXCLUDE:
        if excl in l:
            return False

    # Check US city/region keywords
    for city in US_LOCATIONS:
        if city in l:
            return True

    # Check state abbreviations with word boundaries
    for abbr in US_STATE_ABBREVS:
        if re.search(r'\b' + re.escape(abbr) + r'\b', l):
            return True

    return False


# ─── ROLE CLASSIFICATION ─────────────────────────────────────────────────────

# Categories where Director / Principal / Partner are acceptable seniority
_CONSULTING_LIKE = {"Consulting", "Solutions / Pre-Sales"}

# Categories that use Program Manager patterns — checked against disqualifiers
_PM_CATEGORIES = {"Technical Program Manager", "Product Manager"}


def classify_role(title: str) -> str | None:
    """
    Classify a job title into one of 9 role categories.
    Returns None if the title is disqualified at any stage.

    Pass order:
      1. TITLE_BLACKLIST  — hard-coded non-target role phrases
      2. Category match   — first-match wins (order in ROLE_CATEGORIES matters)
      3. Seniority check  — VP/C-suite always excluded;
                            Director/Principal excluded UNLESS category is
                            Consulting or Solutions/Pre-Sales
      4. Junior check     — intern / co-op / new grad always excluded
         (APM / Associate PM are intentionally NOT in junior list)
      5. PM disqualifier  — Program Manager titles in non-target domains
    """
    t = norm(title)
    if not t:
        return None

    # ── 1. TITLE_BLACKLIST ───────────────────────────────────────────────────
    for phrase in TITLE_BLACKLIST:
        if re.search(r'\b' + re.escape(phrase) + r'\b', t, re.IGNORECASE):
            return None

    # ── 2. Category match ────────────────────────────────────────────────────
    category = None
    for cat, patterns in ROLE_CATEGORIES.items():
        for pattern, _unused in patterns:
            if re.search(pattern, t, re.IGNORECASE):
                category = cat
                break
        if category:
            break

    if category is None:
        return None

    # ── 3. Seniority — always-excluded levels (VP, C-suite, SVP, EVP…) ──────
    for pattern in SENIOR_EXCLUDE_ALWAYS:
        if re.search(pattern, t, re.IGNORECASE):
            return None

    # ── 3b. Seniority — Director/Principal/Partner allowed in Consulting ─────
    if category not in _CONSULTING_LIKE:
        for pattern in SENIOR_EXCLUDE_NON_CONSULTING:
            if re.search(pattern, t, re.IGNORECASE):
                return None

    # ── 4. Junior check ──────────────────────────────────────────────────────
    for pattern in JUNIOR_EXCLUDE_PATTERNS:
        if re.search(pattern, t, re.IGNORECASE):
            return None

    # ── 5. Program Manager disqualifier check ────────────────────────────────
    if category in _PM_CATEGORIES:
        t_lower = t.lower()
        for word in PROGRAM_MANAGER_DISQUALIFIERS:
            if re.search(r'\b' + re.escape(word) + r'\b', t_lower):
                return None

    return category


# ─── EXPERIENCE CHECK ─────────────────────────────────────────────────────────

def experience_ok(description: str) -> bool:
    """Check if JD doesn't require 10+ years experience."""
    d = norm(description)
    return not any(xp in d for xp in XP_DISQUALIFY)


# ─── FRESHNESS FILTER ─────────────────────────────────────────────────────────

def posting_age_ok(posted_date: str) -> bool:
    """
    Reject jobs older than MAX_JOB_AGE_DAYS.
    Also reject future dates. Keep jobs with no date.
    """
    if not posted_date or len(posted_date) < 10:
        return True
    try:
        age = (datetime.now() - datetime.strptime(posted_date[:10], "%Y-%m-%d")).days
        return 0 <= age <= MAX_JOB_AGE_DAYS
    except (ValueError, TypeError):
        return True


# ─── VISA ─────────────────────────────────────────────────────────────────────

def check_visa_sponsor(slug: str) -> str:
    """
    Check visa sponsorship status. Uses exact slug matching.
    """
    s = norm(slug).replace("-", "").replace("_", "")
    # Exact match against known sponsors
    if s in VISA_SPONSORS:
        return "✅ Known Sponsor"
    # Also check if the slug is a prefix/variant of a known sponsor
    for sponsor in VISA_SPONSORS:
        if s == sponsor.replace("-", "").replace("_", ""):
            return "✅ Known Sponsor"
    return "⚠️ Verify"


def clean_location(loc: str) -> str:
    return loc.strip() if loc else "Not specified"
