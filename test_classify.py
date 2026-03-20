"""
test_classify.py — 43 assertions for classify_role()
Run: python3 test_classify.py
"""
import sys
sys.path.insert(0, ".")
from filters import classify_role

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"

cases = [
    # ── Target PM roles ──────────────────────────────────────────────────────
    ("Senior Product Manager",                      "Product Manager"),
    ("Associate Product Manager",                   "Product Manager"),   # APM KEPT
    ("APM, Payments",                               "Product Manager"),   # APM KEPT
    ("Product Manager II",                          "Product Manager"),
    ("Staff PM",                                    None),               # Staff = too senior
    ("Group Product Manager",                       "Product Manager"),
    ("Forward-Deployed Product Manager",            "Product Manager"),
    ("Technical Product Manager",                   "Product Manager"),

    # ── AI/ML PM ─────────────────────────────────────────────────────────────
    ("AI Product Manager",                          "AI/ML Product Manager"),
    ("Product Manager, AI Platform",               "AI/ML Product Manager"),
    ("Product Manager - AI",                        "AI/ML Product Manager"),
    ("ML Product Manager",                          "AI/ML Product Manager"),
    ("Product Manager, Generative AI",              "AI/ML Product Manager"),
    ("Product Manager, LLM",                        "AI/ML Product Manager"),

    # ── Product Marketing ────────────────────────────────────────────────────
    ("Product Marketing Manager",                   "Product Marketing"),
    ("Senior Product Marketing Manager",            "Product Marketing"),
    ("PMM, Enterprise",                             "Product Marketing"),

    # ── TPM ──────────────────────────────────────────────────────────────────
    ("Technical Program Manager",                   "Technical Program Manager"),
    ("Engineering Program Manager",                 "Technical Program Manager"),
    ("TPM, Infrastructure",                         "Technical Program Manager"),
    ("Program Manager, Engineering",                "Technical Program Manager"),
    ("Delivery Manager",                            "Technical Program Manager"),

    # ── Strategy & Ops ───────────────────────────────────────────────────────
    ("Strategy & Operations Manager",               "Strategy & Operations"),
    ("Chief of Staff",                              "Strategy & Operations"),
    ("Chief of Staff to the CEO",                   "Strategy & Operations"),
    ("Revenue Operations Manager",                  "Strategy & Operations"),
    ("BizOps Lead",                                 "Strategy & Operations"),
    ("GTM Strategy Manager",                        "Strategy & Operations"),

    # ── Finance / FP&A ───────────────────────────────────────────────────────
    ("FP&A Manager",                                "Finance & Strategy / FP&A"),
    ("Strategic Finance Manager",                   "Finance & Strategy / FP&A"),
    ("Financial Analyst",                           "Finance & Strategy / FP&A"),

    # ── Consulting (Director/Principal OK) ────────────────────────────────────
    ("Senior Consultant",                           "Consulting"),
    ("Management Consultant",                       "Consulting"),
    ("Associate Consultant",                        "Consulting"),
    ("Principal Consultant",                        "Consulting"),        # principal OK in consulting
    ("Director, Consulting",                        "Consulting"),        # director OK in consulting

    # ── Customer Success ─────────────────────────────────────────────────────
    ("Customer Success Manager",                    "Customer Success"),
    ("CSM, Enterprise",                             "Customer Success"),

    # ── Solutions / Pre-Sales ────────────────────────────────────────────────
    ("Solutions Consultant",                        "Solutions / Pre-Sales"),
    ("Pre-Sales Consultant",                        "Solutions / Pre-Sales"),
    ("Solutions Architect",                         "Solutions / Pre-Sales"),

    # ── Blacklisted (must → None) ────────────────────────────────────────────
    ("ML Engineer - Sr. Consultant Level",          None),   # blacklisted
    ("Software Engineer",                           None),
    ("Data Scientist",                              None),
    ("Sales Engineer",                              None),
    ("Customer Operations Specialist",              None),
    ("Customer Support Lead",                       None),

    # ── Too senior → None (non-consulting) ───────────────────────────────────
    ("VP of Product",                               None),
    ("Vice President, Product Management",          None),
    ("Head of Product",                             None),
    ("Chief Product Officer",                       None),   # Chief X (not Chief of Staff)
    ("Staff Product Manager",                       None),   # staff in PM = too senior
    ("Principal Product Manager",                   None),
    ("Director of Product Management",              None),

    # ── Too junior → None ────────────────────────────────────────────────────
    ("Product Manager Intern",                      None),
    ("New Grad - Product Manager",                  None),
    ("Junior Product Manager",                      None),

    # ── PM disqualifiers → None ──────────────────────────────────────────────
    ("Loyalty Program Manager",                     None),
    ("Benefits Program Manager",                    None),
    ("Affiliate Program Manager",                   None),
    ("Events Program Manager",                      None),
    ("Compensation Program Manager",                None),
    ("Facilities Program Manager",                  None),

    # ── Edge cases ───────────────────────────────────────────────────────────
    ("",                                            None),
    ("Random Job Title",                            None),
]

failures = 0
for title, expected in cases:
    result = classify_role(title)
    ok = result == expected
    if not ok:
        failures += 1
        print(f"  {FAIL}  '{title}'")
        print(f"         expected: {expected!r}")
        print(f"         got:      {result!r}")

total = len(cases)
passed = total - failures
print(f"\n{'─'*50}")
if failures == 0:
    print(f"  {PASS}  All {total} assertions passed")
else:
    print(f"  {FAIL}  {failures}/{total} failed")

sys.exit(1 if failures else 0)
