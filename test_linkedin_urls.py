"""
test_linkedin_urls.py — Verify build_linkedin_urls() output correctness.
Run: python3 test_linkedin_urls.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from dashboard import build_linkedin_urls

PASS = "✅"
FAIL = "❌"
failures = []


def check(label, condition):
    if condition:
        print(f"  {PASS} {label}")
    else:
        print(f"  {FAIL} {label}")
        failures.append(label)


print("\n── Alumni (Stripe) ──")
u = build_linkedin_urls("Stripe", "alumni")
check("Company name quoted (%22Stripe%22)",      "%22Stripe%22" in u["1st"])
check("Kelley School of Business present",       "Kelley+School+of+Business" in u["1st"] or "Kelley%20School%20of%20Business" in u["1st"])
check("Indiana University present",              "Indiana+University" in u["1st"] or "Indiana%20University" in u["1st"])
check("1st degree filter (network=%5B%22F%22%5D)", "network=%5B%22F%22%5D" in u["1st"])
check("2nd degree filter (network=%5B%22S%22%5D)", "network=%5B%22S%22%5D" in u["2nd"])
check("3rd degree filter (network=%5B%22O%22%5D)", "network=%5B%22O%22%5D" in u["3rd"])
check("US geo filter (geoUrn=)",                 "geoUrn=" in u["1st"])

print("\n── Alumni (multi-word company: Palo Alto Networks) ──")
u2 = build_linkedin_urls("Palo Alto Networks", "alumni")
check("Multi-word company encoded correctly",
      "Palo+Alto+Networks" in u2["1st"] or "Palo%20Alto%20Networks" in u2["1st"])
check("Company name quoted",
      "%22Palo+Alto+Networks%22" in u2["1st"] or "%22Palo%20Alto%20Networks%22" in u2["1st"])

print("\n── Hiring team (Datadog, Product Manager) ──")
u3 = build_linkedin_urls("Datadog", "hiring_team", role_category="Product Manager")
kw_part = u3["1st"].split("keywords=")[1].split("&")[0].lower()
check("technical recruiter OR talent acquisition present",
      "technical+recruiter" in kw_part or "talent+acquisition" in kw_part)
check("No bare 'recruiter' keyword outside quoted phrase",
      # After removing known phrases, no standalone 'recruiter' remains
      "recruiter" not in kw_part
          .replace("technical+recruiter", "")
          .replace("talent+acquisition", "")
          .replace("%22recruiter%22", ""))
check("Company Datadog quoted",   "%22Datadog%22" in u3["1st"])
check("US geo filter present",    "geoUrn=" in u3["1st"])

print("\n── Hiring team (Consulting) ──")
u4 = build_linkedin_urls("McKinsey", "hiring_team", role_category="Consulting")
kw4 = u4["1st"].split("keywords=")[1].split("&")[0].lower()
check("talent partner present for Consulting",
      "talent+partner" in kw4 or "talent_partner" in kw4)

print("\n── Same role (title cleaning) ──")
u5 = build_linkedin_urls("Stripe", "same_role",
                          job_title="Senior Product Manager, AI Platform (Remote)")
kw5 = u5["1st"].split("keywords=")[1].split("&")[0].lower()
check("Seniority prefix stripped (no 'senior')", "senior" not in kw5)
check("Location suffix stripped (no 'remote')",  "remote"  not in kw5)
check("Core keyword 'product' present",          "product" in kw5)

print("\n── Same role (no job_title fallback) ──")
u6 = build_linkedin_urls("Acme", "same_role", role_category="Product Manager")
kw6 = u6["1st"].split("keywords=")[1].split("&")[0].lower()
check("Falls back to role_category terms",       "product" in kw6 or "manager" in kw6)

print("\n── Degree links are all distinct ──")
u7 = build_linkedin_urls("Salesforce", "alumni")
check("1st ≠ 2nd", u7["1st"] != u7["2nd"])
check("2nd ≠ 3rd", u7["2nd"] != u7["3rd"])
check("1st ≠ 3rd", u7["1st"] != u7["3rd"])

print()
if failures:
    print(f"FAILED {len(failures)} check(s):")
    for f in failures:
        print(f"  {FAIL} {f}")
    sys.exit(1)
else:
    print(f"All checks passed ✅")
