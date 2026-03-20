"""
db.py — Job Feed v3 Database Layer
SQLite-backed storage replacing flat JSON files.
Supports job persistence, dedup, application tracking, and scoring.
"""
import sqlite3
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from config import DB_PATH


def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: str = DB_PATH):
    """Create tables if they don't exist."""
    conn = get_connection(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS jobs (
            job_id              TEXT PRIMARY KEY,
            date_found          TEXT NOT NULL,
            posted_date         TEXT,
            company             TEXT NOT NULL,
            slug                TEXT,
            role_title          TEXT NOT NULL,
            role_category       TEXT,
            location            TEXT,
            remote              TEXT,
            job_url             TEXT,
            ats_source          TEXT,
            visa_sponsor        TEXT,
            description         TEXT,
            -- Scoring fields
            match_score         REAL DEFAULT 0,
            keyword_hits        TEXT,    -- JSON: {cluster: [matched_keywords]}
            cluster_scores      TEXT,    -- JSON: {cluster: score}
            mba_preferred       INTEGER DEFAULT 0,  -- boolean
            -- Tracking fields
            status              TEXT DEFAULT 'new',
            applied_date        TEXT,
            resume_version      TEXT,
            notes               TEXT,
            last_status_change  TEXT,
            -- Timestamps
            created_at          TEXT DEFAULT (datetime('now')),
            updated_at          TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS contacts (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            company             TEXT NOT NULL,
            name                TEXT NOT NULL,
            title               TEXT,
            linkedin_url        TEXT,
            email               TEXT,
            phone               TEXT,
            source              TEXT,  -- alumni, recruiter, referral, cold, conference
            relationship        TEXT DEFAULT 'cold',  -- cold, warm, connected, replied
            connection_degree   INTEGER,  -- 1, 2, or 3 (LinkedIn degree)
            intro_through       TEXT,     -- name of mutual connection
            last_contacted      TEXT,
            next_followup       TEXT,
            total_touchpoints   INTEGER DEFAULT 0,
            notes               TEXT,
            enrichment_data     TEXT,     -- JSON: raw API response
            enriched_via        TEXT,     -- "apollo", "clay", "manual"
            linked_job_id       TEXT,     -- optional FK to a specific job
            created_at          TEXT DEFAULT (datetime('now')),
            updated_at          TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS touchpoints (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            contact_id      INTEGER NOT NULL,
            touchpoint_date TEXT NOT NULL,
            channel         TEXT,   -- email, linkedin, phone, in-person
            direction       TEXT,   -- outbound, inbound
            subject         TEXT,
            notes           TEXT,
            created_at      TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (contact_id) REFERENCES contacts(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS feed_runs (
            run_id          INTEGER PRIMARY KEY AUTOINCREMENT,
            run_date        TEXT NOT NULL,
            source_counts   TEXT,    -- JSON: {source: count}
            total_fetched   INTEGER DEFAULT 0,
            total_new       INTEGER DEFAULT 0,
            total_filtered  INTEGER DEFAULT 0,
            duration_secs   REAL,
            errors          TEXT,    -- JSON: [{source, slug, error}]
            created_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
        CREATE INDEX IF NOT EXISTS idx_jobs_category ON jobs(role_category);
        CREATE INDEX IF NOT EXISTS idx_jobs_date ON jobs(date_found);
        CREATE INDEX IF NOT EXISTS idx_jobs_score ON jobs(match_score DESC);
        CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company);
        CREATE INDEX IF NOT EXISTS idx_contacts_company ON contacts(company);
        CREATE INDEX IF NOT EXISTS idx_touchpoints_contact ON touchpoints(contact_id);
    """)
    conn.commit()

    # ── Migrate existing contacts table to add enrichment columns ─────────────
    existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(contacts)")}
    new_cols = {
        "phone":             "TEXT",
        "connection_degree": "INTEGER",
        "intro_through":     "TEXT",
        "total_touchpoints": "INTEGER DEFAULT 0",
        "enrichment_data":   "TEXT",
        "enriched_via":      "TEXT",
    }
    for col, col_type in new_cols.items():
        if col not in existing_cols:
            conn.execute(f"ALTER TABLE contacts ADD COLUMN {col} {col_type}")
    conn.commit()
    conn.close()


def get_seen_ids(db_path: str = DB_PATH) -> set:
    """Get all known job IDs for deduplication."""
    conn = get_connection(db_path)
    rows = conn.execute("SELECT job_id FROM jobs").fetchall()
    conn.close()
    return {r["job_id"] for r in rows}


def insert_jobs(jobs: list[dict], db_path: str = DB_PATH) -> int:
    """Insert new jobs, skip duplicates. Returns count inserted."""
    if not jobs:
        return 0
    conn = get_connection(db_path)
    inserted = 0
    for job in jobs:
        try:
            conn.execute("""
                INSERT OR IGNORE INTO jobs (
                    job_id, date_found, posted_date, company, slug,
                    role_title, role_category, location, remote,
                    job_url, ats_source, visa_sponsor, description,
                    match_score, keyword_hits, cluster_scores, mba_preferred
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job["job_id"],
                job.get("date_found", datetime.now(timezone.utc).strftime("%Y-%m-%d")),
                job.get("posted_date"),
                job.get("company", ""),
                job.get("slug", ""),
                job.get("role_title", ""),
                job.get("role_category"),
                job.get("location"),
                job.get("remote"),
                job.get("job_url"),
                job.get("ats_source"),
                job.get("visa_sponsor"),
                job.get("description"),
                job.get("match_score", 0),
                json.dumps(job.get("keyword_hits", {})),
                json.dumps(job.get("cluster_scores", {})),
                1 if job.get("mba_preferred") else 0,
            ))
            if conn.total_changes:
                inserted += 1
        except sqlite3.IntegrityError:
            pass
    conn.commit()
    conn.close()
    return inserted


def update_job_score(job_id: str, score: float, keyword_hits: dict,
                     cluster_scores: dict, mba_preferred: bool = False,
                     db_path: str = DB_PATH):
    conn = get_connection(db_path)
    conn.execute("""
        UPDATE jobs SET
            match_score = ?,
            keyword_hits = ?,
            cluster_scores = ?,
            mba_preferred = ?,
            updated_at = datetime('now')
        WHERE job_id = ?
    """, (score, json.dumps(keyword_hits), json.dumps(cluster_scores),
          1 if mba_preferred else 0, job_id))
    conn.commit()
    conn.close()


def update_job_status(job_id: str, status: str, notes: str = None,
                      resume_version: str = None, db_path: str = DB_PATH):
    conn = get_connection(db_path)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    fields = ["status = ?", "updated_at = datetime('now')",
              "last_status_change = ?"]
    values = [status, now]
    if status == "applied":
        fields.append("applied_date = ?")
        values.append(now)
    if notes is not None:
        fields.append("notes = ?")
        values.append(notes)
    if resume_version is not None:
        fields.append("resume_version = ?")
        values.append(resume_version)
    values.append(job_id)
    conn.execute(f"UPDATE jobs SET {', '.join(fields)} WHERE job_id = ?", values)
    conn.commit()
    conn.close()


def get_jobs(status: str = None, category: str = None, min_score: float = None,
             days: int = None, limit: int = 500, db_path: str = DB_PATH) -> list[dict]:
    """Query jobs with optional filters."""
    conn = get_connection(db_path)
    where = []
    params = []
    if status:
        where.append("status = ?")
        params.append(status)
    if category:
        where.append("role_category = ?")
        params.append(category)
    if min_score is not None:
        where.append("match_score >= ?")
        params.append(min_score)
    if days is not None:
        where.append("date_found >= date('now', ?)")
        params.append(f"-{days} days")

    clause = f"WHERE {' AND '.join(where)}" if where else ""
    rows = conn.execute(
        f"SELECT * FROM jobs {clause} ORDER BY match_score DESC, posted_date DESC LIMIT ?",
        params + [limit]
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_today_jobs(db_path: str = DB_PATH) -> list[dict]:
    """Get jobs found today."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return get_jobs(days=0, db_path=db_path)


def get_stats(days: int = 7, db_path: str = DB_PATH) -> dict:
    """Get summary statistics."""
    conn = get_connection(db_path)
    cutoff = f"-{days} days"

    total = conn.execute(
        "SELECT COUNT(*) FROM jobs WHERE date_found >= date('now', ?)", (cutoff,)
    ).fetchone()[0]
    by_cat = conn.execute(
        "SELECT role_category, COUNT(*) as cnt FROM jobs "
        "WHERE date_found >= date('now', ?) GROUP BY role_category ORDER BY cnt DESC",
        (cutoff,)
    ).fetchall()
    by_status = conn.execute(
        "SELECT status, COUNT(*) as cnt FROM jobs "
        "WHERE date_found >= date('now', ?) GROUP BY status ORDER BY cnt DESC",
        (cutoff,)
    ).fetchall()
    by_source = conn.execute(
        "SELECT ats_source, COUNT(*) as cnt FROM jobs "
        "WHERE date_found >= date('now', ?) GROUP BY ats_source ORDER BY cnt DESC",
        (cutoff,)
    ).fetchall()
    visa_cnt = conn.execute(
        "SELECT COUNT(*) FROM jobs WHERE date_found >= date('now', ?) "
        "AND visa_sponsor LIKE '%Known%'", (cutoff,)
    ).fetchone()[0]
    avg_score = conn.execute(
        "SELECT AVG(match_score) FROM jobs WHERE date_found >= date('now', ?) "
        "AND match_score > 0", (cutoff,)
    ).fetchone()[0] or 0

    conn.close()
    return {
        "total": total,
        "by_category": {r["role_category"]: r["cnt"] for r in by_cat},
        "by_status": {r["status"]: r["cnt"] for r in by_status},
        "by_source": {r["ats_source"]: r["cnt"] for r in by_source},
        "visa_sponsors": visa_cnt,
        "avg_match_score": round(avg_score, 1),
    }


def log_run(source_counts: dict, total_fetched: int, total_new: int,
            total_filtered: int, duration_secs: float, errors: list,
            db_path: str = DB_PATH):
    conn = get_connection(db_path)
    conn.execute("""
        INSERT INTO feed_runs (run_date, source_counts, total_fetched,
                              total_new, total_filtered, duration_secs, errors)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        json.dumps(source_counts),
        total_fetched, total_new, total_filtered,
        round(duration_secs, 2),
        json.dumps(errors) if errors else None,
    ))
    conn.commit()
    conn.close()


def migrate_from_json(seen_path: str, jobs_json_path: str = None,
                      db_path: str = DB_PATH):
    """One-time migration from flat JSON files to SQLite."""
    init_db(db_path)

    # Migrate seen_jobs.json as skeleton records
    if os.path.exists(seen_path):
        seen_ids = json.load(open(seen_path))
        conn = get_connection(db_path)
        for jid in seen_ids:
            try:
                # Parse what we can from the ID format: gh_slug_12345
                parts = jid.split("_", 2)
                source_map = {"gh": "Greenhouse", "lv": "Lever",
                              "ash": "Ashby", "sr": "SmartRecruiters"}
                source = source_map.get(parts[0], "Unknown") if len(parts) >= 2 else "Unknown"
                slug = parts[1] if len(parts) >= 2 else ""
                company = slug.replace("-", " ").title()

                conn.execute("""
                    INSERT OR IGNORE INTO jobs (job_id, date_found, company, slug,
                                               role_title, ats_source, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (jid, "2026-03-12", company, slug, "(migrated)", source, "expired"))
            except Exception:
                pass
        conn.commit()
        conn.close()
        print(f"  Migrated {len(seen_ids)} seen IDs from {seen_path}")

    # Migrate jobs_today.json with full data
    if jobs_json_path and os.path.exists(jobs_json_path):
        jobs = json.load(open(jobs_json_path))
        inserted = insert_jobs(jobs, db_path)
        print(f"  Migrated {inserted} active jobs from {jobs_json_path}")


# ─── CONTACTS ─────────────────────────────────────────────────────────────────

def get_contacts(company: str = None, db_path: str = DB_PATH) -> list[dict]:
    conn = get_connection(db_path)
    if company:
        rows = conn.execute(
            "SELECT * FROM contacts WHERE company = ? ORDER BY updated_at DESC",
            (company,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM contacts ORDER BY updated_at DESC"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def insert_contact(contact: dict, db_path: str = DB_PATH) -> int:
    conn = get_connection(db_path)
    cur = conn.execute("""
        INSERT INTO contacts (company, name, title, linkedin_url, email,
                              source, relationship, last_contacted, next_followup,
                              notes, linked_job_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        contact.get("company", ""),
        contact.get("name", ""),
        contact.get("title"),
        contact.get("linkedin_url"),
        contact.get("email"),
        contact.get("source"),
        contact.get("relationship", "cold"),
        contact.get("last_contacted"),
        contact.get("next_followup"),
        contact.get("notes"),
        contact.get("linked_job_id"),
    ))
    new_id = cur.lastrowid
    conn.commit()
    conn.close()
    return new_id


def update_contact(contact_id: int, updates: dict, db_path: str = DB_PATH):
    allowed = {"relationship", "last_contacted", "next_followup", "notes",
               "title", "linkedin_url", "email", "source", "company", "name"}
    fields = []
    values = []
    for k, v in updates.items():
        if k in allowed:
            fields.append(f"{k} = ?")
            values.append(v)
    if not fields:
        return
    fields.append("updated_at = datetime('now')")
    values.append(contact_id)
    conn = get_connection(db_path)
    conn.execute(
        f"UPDATE contacts SET {', '.join(fields)} WHERE id = ?", values
    )
    conn.commit()
    conn.close()


def delete_contact(contact_id: int, db_path: str = DB_PATH):
    conn = get_connection(db_path)
    conn.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))
    conn.commit()
    conn.close()


# ─── TOUCHPOINTS ──────────────────────────────────────────────────────────────

def log_touchpoint(contact_id: int, channel: str, direction: str = "outbound",
                   subject: str = None, notes: str = None,
                   db_path: str = DB_PATH) -> int:
    """Log a new outreach touchpoint and increment contact's total_touchpoints."""
    conn = get_connection(db_path)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    cur = conn.execute("""
        INSERT INTO touchpoints (contact_id, touchpoint_date, channel, direction,
                                  subject, notes)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (contact_id, today, channel, direction, subject, notes))
    new_id = cur.lastrowid
    # Update last_contacted + total_touchpoints
    conn.execute("""
        UPDATE contacts
        SET last_contacted = ?,
            total_touchpoints = COALESCE(total_touchpoints, 0) + 1,
            updated_at = datetime('now')
        WHERE id = ?
    """, (today, contact_id))
    conn.commit()
    conn.close()
    return new_id


def get_touchpoints(contact_id: int, db_path: str = DB_PATH) -> list[dict]:
    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT * FROM touchpoints WHERE contact_id = ? ORDER BY touchpoint_date DESC",
        (contact_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def apply_enrichment(contact_id: int, enrichment: dict, db_path: str = DB_PATH):
    """Write enrichment results back to the contacts row."""
    allowed = {"email", "phone", "title", "linkedin_url",
               "connection_degree", "enrichment_data", "enriched_via"}
    fields = []
    values = []
    for k, v in enrichment.items():
        if k in allowed and v is not None:
            fields.append(f"{k} = ?")
            val = json.dumps(v) if k == "enrichment_data" and isinstance(v, dict) else v
            values.append(val)
    if not fields:
        return
    fields.append("updated_at = datetime('now')")
    values.append(contact_id)
    conn = get_connection(db_path)
    conn.execute(f"UPDATE contacts SET {', '.join(fields)} WHERE id = ?", values)
    conn.commit()
    conn.close()
