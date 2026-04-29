# Job Feed Dashboard

A freshness-first job search dashboard that tracks newly posted roles from 300+ companies, scores each opportunity based on fit, and manages the full application pipeline from discovery to networking.

Built for MBA candidates who want to move faster on high-fit roles across Greenhouse, Lever, Ashby, SmartRecruiters, and Workday.

_The core value proposition is speed: the dashboard surfaces only new and recently posted roles, so users can apply and network while the opportunity is less crowded._
----

## Impact

- Aggregates roles from 300+ target companies across multiple ATS platforms.
- Scores jobs from 0–100 using keyword clusters, role fit, visa signals, freshness, and MBA relevance.
- Converts a manual spreadsheet-based job search into a searchable dashboard and Kanban pipeline.
- Supports networking workflows with LinkedIn links, contact tracking, and outreach CRM.

----
## Screenshots

### Daily job feed email

<p align="center">
  <img width="500" alt="Daily job feed email preview" src="https://github.com/user-attachments/assets/5fa1d6c0-6e31-447f-a7f9-59132371cae0" />
</p>

### Dashboard summary

<p align="center">
  <img width="650" alt="Job feed dashboard summary" src="https://github.com/user-attachments/assets/f5b8fafe-980c-4420-88e3-f1ee481a1387" />
</p>

### Role category breakdown

<p align="center">
  <img width="650" alt="Job feed role category breakdown" src="https://github.com/user-attachments/assets/ed6faca2-4be0-4b93-b404-62e082631b4a" />
</p>

----

## Quick Start

```bash
git clone <repo>
cd job_feed_v3
python3 -m venv venv
source venv/bin/activate
pip install flask requests openpyxl
python3 dashboard.py
```

Open http://localhost:5050

## What It Does

- Scrapes 300+ companies across Greenhouse, Lever, Ashby, SmartRecruiters, and Workday
- Filters for PM, TPM, AI/ML PM, Strategy & Ops, FP&A, and Consulting roles
- Scores each job 0-100 against keyword clusters (+ 🎓 +15 MBA/Master's bonus)
- Kanban pipeline for application tracking
- LinkedIn networking links + outreach CRM
- One-click resume rebase prompt generation
- Excel export with all tabs

## Usage

- **"Fetch Now"** button to pull latest jobs
- **"Discover"** tab to browse and save jobs (sorted by score, status=new only)
- **"Pipeline"** tab to track applications (Kanban: Saved → Applying → Applied → Interviewing → Offer)
- **"Network"** tab to find connections and track outreach contacts
- **"Export Excel"** for the full spreadsheet with all category tabs + Network sheet

## Role Categories

| Category | Example Titles |
|---|---|
| Product Manager | Senior PM, Group Product Manager |
| AI/ML Product Manager | Product Manager, AI Platform |
| Technical Program Manager | TPM, Engineering Program Manager |

## Scoring

Each job is scored 0-100 based on:
- **Keyword match (45%)**: Relevant keywords from 11 clusters in the JD
- **Category fit (20%)**: Title matched a target role category
- **Visa sponsor (10%)**: Known H1B sponsor = 100, unknown = 30
- **Freshness (10%)**: Today = 100, 3 days = 80, 7 days = 50
- **MBA bonus (+15 flat)**: If JD mentions "MBA preferred" / "Master's required" etc.

## File Structure

```
job_feed_v3/
├── config.py           # All constants, company lists, role taxonomy
├── filters.py          # Role classification, location, seniority, freshness
├── fetchers.py         # ATS API fetchers (GH, Lever, Ashby, SR, Workday)
├── scorer.py           # JD keyword scoring + MBA signal detection
├── db.py               # SQLite database layer (jobs + contacts tables)
├── build_excel_v3.py   # Excel builder with MBA badges + Network sheet
├── job_feed.py         # Main orchestrator (fetch → score → save)
├── dashboard.py        # Flask dashboard (Discover / Pipeline / Network)
├── setup.sh            # Dependency installer
└── README.md
```
