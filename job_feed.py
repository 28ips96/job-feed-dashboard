"""
job_feed.py — Job Feed v3 Main Orchestrator
Usage:
    python3 job_feed.py              # Full daily run
    python3 job_feed.py --migrate    # One-time migration from v2
    python3 job_feed.py --stats      # Print stats
    python3 job_feed.py --rescore    # Re-score all jobs with current clusters
"""
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from config import (
    FEED_DIR, OUTPUT_DIR, DB_PATH, KEYWORDS_PATH, LOG_FILE,
    GREENHOUSE_SLUGS, LEVER_SLUGS, ASHBY_SLUGS,
    SMARTRECRUITERS_SLUGS, WORKDAY_COMPANIES,
)
from db import (
    init_db, get_seen_ids, insert_jobs, log_run,
    get_jobs, get_stats, migrate_from_json, update_job_score,
)
from fetchers import fetch_all
from scorer import load_keyword_clusters, score_batch, score_job
from build_excel_v3 import build_excel

# ─── LOGGING ──────────────────────────────────────────────────────────────────

def setup_logging():
    log = logging.getLogger("job_feed")
    log.setLevel(logging.INFO)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # File handler
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setFormatter(fmt)
    log.addHandler(fh)

    # Console handler
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    log.addHandler(ch)

    return log


# ─── MAIN RUN ─────────────────────────────────────────────────────────────────

def run_feed():
    log = setup_logging()
    log.info("=" * 60)
    log.info("Job Feed v3 — Starting daily run")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    init_db()

    start = time.time()

    # 1. Fetch from all sources (concurrent)
    log.info("Step 1: Fetching jobs...")
    all_jobs, all_errors, source_counts = fetch_all(
        greenhouse_slugs=GREENHOUSE_SLUGS,
        lever_slugs=LEVER_SLUGS,
        ashby_slugs=ASHBY_SLUGS,
        smartrecruiters_slugs=SMARTRECRUITERS_SLUGS,
        workday_companies=WORKDAY_COMPANIES,
        max_workers=12,
    )
    total_fetched = len(all_jobs)

    # 2. Deduplicate against DB
    log.info("Step 2: Deduplicating...")
    seen = get_seen_ids()
    seen_this_run = set()
    new_jobs = []
    for job in all_jobs:
        jid = job["job_id"]
        if jid not in seen and jid not in seen_this_run:
            new_jobs.append(job)
            seen_this_run.add(jid)
    log.info(f"  {len(new_jobs)} new jobs (filtered from {total_fetched})")

    # 3. Score new jobs
    log.info("Step 3: Scoring...")
    clusters = load_keyword_clusters(KEYWORDS_PATH)
    scored_jobs = score_batch(new_jobs, clusters)
    high_fit = sum(1 for j in scored_jobs if j.get("match_score", 0) >= 70)
    log.info(f"  {high_fit} high-fit (70+) out of {len(scored_jobs)}")

    # 4. Insert into DB
    log.info("Step 4: Saving to database...")
    inserted = insert_jobs(scored_jobs)
    log.info(f"  {inserted} jobs inserted")

    # 5. Build Excel
    log.info("Step 5: Building Excel...")
    today = datetime.now().strftime("%Y-%m-%d")
    excel_path = os.path.join(OUTPUT_DIR, f"job_feed_{today}.xlsx")
    # Include all jobs from last 7 days for the Excel
    recent_jobs = get_jobs(days=7)
    build_excel(recent_jobs, excel_path)

    # 7. Log the run
    duration = time.time() - start
    log_run(
        source_counts=source_counts,
        total_fetched=total_fetched,
        total_new=len(new_jobs),
        total_filtered=total_fetched - len(new_jobs),
        duration_secs=duration,
        errors=all_errors,
    )

    # Summary
    log.info(f"\n{'─' * 50}")
    log.info(f"✅ Run complete in {duration:.1f}s")
    log.info(f"   Fetched: {total_fetched} | New: {len(new_jobs)} | "
             f"High-fit: {high_fit} | Errors: {len(all_errors)}")
    if all_errors:
        log.info(f"   Errors: {len(all_errors)} "
                 f"(check feed_runs table for details)")
    log.info(f"   Excel: {excel_path}")

    return scored_jobs, excel_path




# ─── CLI COMMANDS ─────────────────────────────────────────────────────────────

def cmd_migrate():
    """Migrate from v2 flat files to v3 SQLite."""
    print("Migrating from v2 to v3...")
    init_db()
    seen_path = os.path.join(FEED_DIR, "seen_jobs.json")
    jobs_path = os.path.join(FEED_DIR, "jobs_today.json")
    migrate_from_json(seen_path, jobs_path)
    print("✅ Migration complete. DB at:", DB_PATH)


def cmd_stats():
    """Print current stats."""
    init_db()
    stats = get_stats(days=7)
    print(f"\n📊 Job Feed Stats (last 7 days)")
    print(f"   Total jobs: {stats['total']}")
    print(f"   Avg score:  {stats['avg_match_score']}")
    print(f"   Visa sponsors: {stats['visa_sponsors']}")
    print(f"\n   By category:")
    for cat, cnt in stats["by_category"].items():
        print(f"     {cat}: {cnt}")
    print(f"\n   By source:")
    for src, cnt in stats["by_source"].items():
        print(f"     {src}: {cnt}")
    print(f"\n   By status:")
    for st, cnt in stats["by_status"].items():
        print(f"     {st}: {cnt}")


def cmd_rescore():
    """Re-score all jobs in DB with current keyword clusters."""
    init_db()
    clusters = load_keyword_clusters(KEYWORDS_PATH)
    jobs = get_jobs(limit=5000)
    print(f"Re-scoring {len(jobs)} jobs...")
    scored = 0
    for job in jobs:
        if job.get("description"):
            score, hits, c_scores, mba = score_job(job, clusters)
            update_job_score(job["job_id"], score, hits, c_scores, mba)
            scored += 1
    print(f"✅ Re-scored {scored} jobs with descriptions")


if __name__ == "__main__":
    if "--migrate" in sys.argv:
        cmd_migrate()
    elif "--stats" in sys.argv:
        cmd_stats()
    elif "--rescore" in sys.argv:
        cmd_rescore()
    else:
        run_feed()
