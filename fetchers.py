"""
fetchers.py — Job Feed v3 ATS Fetchers
Greenhouse, Lever, Ashby, SmartRecruiters, Workday.
Proper error handling, retry logic, concurrent execution.
"""
import requests
import time
import logging
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from filters import classify_role, location_ok, experience_ok, posting_age_ok, check_visa_sponsor, clean_location, norm

log = logging.getLogger("job_feed")


# ─── HTTP SESSION WITH RETRY ─────────────────────────────────────────────────

def _make_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({
        "User-Agent": "JobFeed/3.0 (career-search-tool)",
        "Accept": "application/json",
    })
    return session


_session = _make_session()
TIMEOUT = 15


# ─── HELPER ───────────────────────────────────────────────────────────────────

def _make_job(job_id: str, slug: str, title: str, category: str,
              location: str, remote: bool, url: str, source: str,
              posted_date: str = "", description: str = "") -> dict:
    return {
        "job_id": job_id,
        "date_found": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "posted_date": posted_date,
        "company": slug.replace("-", " ").title(),
        "slug": slug,
        "role_title": title,
        "role_category": category,
        "location": clean_location(location),
        "remote": "Yes 🌐" if remote else "Check listing",
        "job_url": url,
        "ats_source": source,
        "visa_sponsor": check_visa_sponsor(slug),
        "description": description[:5000] if description else "",  # Cap size
    }


# ─── GREENHOUSE ───────────────────────────────────────────────────────────────

def fetch_greenhouse(slug: str) -> tuple[list[dict], list[dict]]:
    """Returns (jobs, errors)."""
    errors = []
    try:
        r = _session.get(
            f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true",
            timeout=TIMEOUT)
        if r.status_code != 200:
            errors.append({"source": "Greenhouse", "slug": slug,
                          "error": f"HTTP {r.status_code}"})
            return [], errors

        jobs = []
        for job in r.json().get("jobs", []):
            title = job.get("title", "")
            cat = classify_role(title)
            if not cat:
                continue
            loc = job.get("location", {}).get("name", "")
            if not location_ok(loc):
                continue
            desc = job.get("content", "") or ""
            if not experience_ok(desc):
                continue
            posted_date = (job.get("updated_at", "") or "")[:10]
            if not posting_age_ok(posted_date):
                continue
            jobs.append(_make_job(
                job_id=f"gh_{slug}_{job.get('id')}",
                slug=slug, title=title, category=cat,
                location=loc,
                remote="remote" in norm(loc),
                url=job.get("absolute_url", ""),
                source="Greenhouse",
                posted_date=posted_date,
                description=desc,
            ))
        return jobs, errors

    except requests.Timeout:
        errors.append({"source": "Greenhouse", "slug": slug, "error": "Timeout"})
        return [], errors
    except Exception as e:
        errors.append({"source": "Greenhouse", "slug": slug, "error": str(e)[:200]})
        return [], errors


# ─── LEVER ────────────────────────────────────────────────────────────────────

def fetch_lever(slug: str) -> tuple[list[dict], list[dict]]:
    errors = []
    try:
        r = _session.get(
            f"https://api.lever.co/v0/postings/{slug}?mode=json",
            timeout=TIMEOUT)
        if r.status_code != 200:
            errors.append({"source": "Lever", "slug": slug,
                          "error": f"HTTP {r.status_code}"})
            return [], errors

        jobs = []
        for job in r.json():
            title = job.get("text", "")
            cat = classify_role(title)
            if not cat:
                continue
            loc = job.get("categories", {}).get("location", "") or \
                  job.get("categories", {}).get("allLocations", "")
            if isinstance(loc, list):
                loc = ", ".join(loc)
            if not location_ok(loc):
                continue
            desc = str(job.get("descriptionBody", "") or "") + \
                   str(job.get("lists", "") or "")
            if not experience_ok(desc):
                continue

            posted = ""
            if job.get("createdAt"):
                try:
                    posted = datetime.fromtimestamp(
                        job["createdAt"] / 1000, tz=timezone.utc
                    ).strftime("%Y-%m-%d")
                except Exception:
                    pass
            if not posting_age_ok(posted):
                continue

            jobs.append(_make_job(
                job_id=f"lv_{slug}_{job.get('id')}",
                slug=slug, title=title, category=cat,
                location=loc,
                remote="remote" in norm(loc),
                url=job.get("hostedUrl", ""),
                source="Lever",
                posted_date=posted,
                description=desc,
            ))
        return jobs, errors

    except requests.Timeout:
        errors.append({"source": "Lever", "slug": slug, "error": "Timeout"})
        return [], errors
    except Exception as e:
        errors.append({"source": "Lever", "slug": slug, "error": str(e)[:200]})
        return [], errors


# ─── ASHBY ────────────────────────────────────────────────────────────────────

def fetch_ashby(slug: str) -> tuple[list[dict], list[dict]]:
    errors = []
    try:
        r = _session.get(
            f"https://api.ashbyhq.com/posting-api/job-board/{slug}",
            timeout=TIMEOUT)
        if r.status_code != 200:
            errors.append({"source": "Ashby", "slug": slug,
                          "error": f"HTTP {r.status_code}"})
            return [], errors

        jobs = []
        for job in r.json().get("jobs", []):
            if not job.get("isListed", True):
                continue
            title = job.get("title", "")
            cat = classify_role(title)
            if not cat:
                continue
            is_remote = job.get("isRemote", False)
            loc = "Remote" if is_remote else (job.get("location", "") or "")
            if not location_ok(loc):
                continue
            desc = job.get("descriptionPlain", "") or ""
            if not experience_ok(desc):
                continue
            posted_date = (job.get("publishedAt", "") or "")[:10]
            if not posting_age_ok(posted_date):
                continue

            jobs.append(_make_job(
                job_id=f"ash_{slug}_{job.get('id', '')}",
                slug=slug, title=title, category=cat,
                location=loc,
                remote=is_remote,
                url=job.get("jobUrl", ""),
                source="Ashby",
                posted_date=posted_date,
                description=desc,
            ))
        return jobs, errors

    except requests.Timeout:
        errors.append({"source": "Ashby", "slug": slug, "error": "Timeout"})
        return [], errors
    except Exception as e:
        errors.append({"source": "Ashby", "slug": slug, "error": str(e)[:200]})
        return [], errors


# ─── SMARTRECRUITERS ──────────────────────────────────────────────────────────

def fetch_smartrecruiters(slug: str) -> tuple[list[dict], list[dict]]:
    errors = []
    try:
        r = _session.get(
            f"https://api.smartrecruiters.com/v1/companies/{slug}/postings",
            params={"limit": 100},
            timeout=TIMEOUT)
        if r.status_code != 200:
            errors.append({"source": "SmartRecruiters", "slug": slug,
                          "error": f"HTTP {r.status_code}"})
            return [], errors

        jobs = []
        for job in r.json().get("content", []):
            title = job.get("name", "")
            cat = classify_role(title)
            if not cat:
                continue
            loc_obj = job.get("location", {})
            city = loc_obj.get("city", "") or ""
            region = loc_obj.get("region", "") or ""
            country = loc_obj.get("country", "") or ""
            remote = (job.get("typeOfEmployment", "") == "REMOTE" or
                     loc_obj.get("remote", False))
            loc_str = "Remote" if remote else ", ".join(filter(None, [city, region, country]))
            if not location_ok(loc_str):
                continue
            desc = (job.get("jobAd", {}).get("sections", {})
                   .get("jobDescription", {}).get("text", "") or "")
            if not experience_ok(desc):
                continue
            sr_posted = (job.get("releasedDate", "") or "")[:10]
            if not posting_age_ok(sr_posted):
                continue

            job_id = job.get("id", "")
            jobs.append(_make_job(
                job_id=f"sr_{slug}_{job_id}",
                slug=slug, title=title, category=cat,
                location=loc_str,
                remote=remote,
                url=f"https://jobs.smartrecruiters.com/{slug}/{job_id}",
                source="SmartRecruiters",
                posted_date=sr_posted,
                description=desc,
            ))
        return jobs, errors

    except requests.Timeout:
        errors.append({"source": "SmartRecruiters", "slug": slug, "error": "Timeout"})
        return [], errors
    except Exception as e:
        errors.append({"source": "SmartRecruiters", "slug": slug, "error": str(e)[:200]})
        return [], errors


# ─── WORKDAY ──────────────────────────────────────────────────────────────────

def fetch_workday(company_name: str, tenant: str, site: str) -> tuple[list[dict], list[dict]]:
    """
    Fetch from Workday job search API.
    Workday uses a POST-based search endpoint.
    """
    errors = []
    slug = tenant.lower()

    # Workday's job search API
    base_url = f"https://{tenant}.wd5.myworkdayjobs.com"
    search_url = f"{base_url}/wday/cxs/{tenant}/{site}/jobs"

    try:
        # Search with broad keywords to get PM/TPM/Strategy/Finance roles
        search_terms = [
            "product manager", "program manager",
            "strategy operations", "financial analyst", "FP&A",
        ]

        all_jobs = []
        seen_ids = set()

        for term in search_terms:
            payload = {
                "appliedFacets": {},
                "limit": 20,
                "offset": 0,
                "searchText": term,
            }
            r = _session.post(search_url, json=payload, timeout=TIMEOUT)
            if r.status_code != 200:
                continue

            data = r.json()
            for posting in data.get("jobPostings", []):
                ext_path = posting.get("externalPath", "")
                wday_id = posting.get("bulletFields", [""])[0] if posting.get("bulletFields") else ext_path
                job_id = f"wd_{slug}_{hash(ext_path) % 10**8}"

                if job_id in seen_ids:
                    continue
                seen_ids.add(job_id)

                title = posting.get("title", "")
                cat = classify_role(title)
                if not cat:
                    continue

                loc = posting.get("locationsText", "") or ""
                if not location_ok(loc):
                    continue

                posted = (posting.get("postedOn", "") or "")[:10]
                if not posting_age_ok(posted):
                    continue

                # Fetch individual job description (Workday search doesn't include JD)
                desc = ""
                try:
                    detail_url = f"{base_url}/wday/cxs/{tenant}/{site}/jobs/{ext_path.lstrip('/')}"
                    dr = _session.get(detail_url, timeout=TIMEOUT)
                    if dr.status_code == 200:
                        ddata = dr.json()
                        desc = (ddata.get("jobPostingInfo", {})
                                .get("jobDescription", "") or "")
                except Exception:
                    pass

                if not experience_ok(desc):
                    continue

                all_jobs.append(_make_job(
                    job_id=job_id,
                    slug=slug, title=title, category=cat,
                    location=loc,
                    remote="remote" in norm(loc),
                    url=f"{base_url}/en-US/{site}{ext_path}",
                    source="Workday",
                    posted_date=posted,
                    description=desc,
                ))



        return all_jobs, errors

    except requests.Timeout:
        errors.append({"source": "Workday", "slug": slug, "error": "Timeout"})
        return [], errors
    except Exception as e:
        errors.append({"source": "Workday", "slug": slug, "error": str(e)[:200]})
        return [], errors


# ─── PARALLEL RUNNER ──────────────────────────────────────────────────────────

def fetch_all(greenhouse_slugs: list, lever_slugs: list, ashby_slugs: list,
              smartrecruiters_slugs: list, workday_companies: list,
              max_workers: int = 10) -> tuple[list[dict], list[dict], dict]:
    """
    Fetch from all sources concurrently.
    Returns (all_jobs, all_errors, source_counts).
    """
    all_jobs = []
    all_errors = []
    source_counts = {}

    tasks = []

    # Build task list: (fetcher_func, args, source_label)
    for slug in greenhouse_slugs:
        tasks.append((fetch_greenhouse, (slug,), "Greenhouse"))
    for slug in lever_slugs:
        tasks.append((fetch_lever, (slug,), "Lever"))
    for slug in ashby_slugs:
        tasks.append((fetch_ashby, (slug,), "Ashby"))
    for slug in smartrecruiters_slugs:
        tasks.append((fetch_smartrecruiters, (slug,), "SmartRecruiters"))
    for company_name, tenant, site in workday_companies:
        tasks.append((fetch_workday, (company_name, tenant, site), "Workday"))

    log.info(f"Fetching from {len(tasks)} company endpoints "
             f"(max {max_workers} concurrent)...")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for fetcher, args, source in tasks:
            future = executor.submit(fetcher, *args)
            futures[future] = (args, source)

        for future in as_completed(futures):
            args, source = futures[future]
            slug = args[0] if args else "unknown"
            try:
                jobs, errs = future.result(timeout=30)
                all_jobs.extend(jobs)
                all_errors.extend(errs)
                if jobs:
                    source_counts[source] = source_counts.get(source, 0) + len(jobs)
                    log.info(f"  ✓ {source}/{slug}: {len(jobs)} roles")
                if errs:
                    for e in errs:
                        log.warning(f"  ⚠️ {e['source']}/{e['slug']}: {e['error']}")
            except Exception as e:
                all_errors.append({"source": source, "slug": slug,
                                  "error": f"Future error: {str(e)[:200]}"})
                log.error(f"  ✗ {source}/{slug}: {e}")

    log.info(f"Fetch complete: {len(all_jobs)} roles from "
             f"{sum(source_counts.values())} matches across "
             f"{len(source_counts)} sources")

    return all_jobs, all_errors, source_counts
