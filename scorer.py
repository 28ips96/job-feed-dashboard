"""
scorer.py — Job Feed v3 JD Keyword Scoring Engine
Scores job descriptions against keyword clusters.
Produces composite match % and per-cluster breakdown.
"""
import re
import json
import os
from datetime import datetime, timezone
from config import SCORE_WEIGHTS, VISA_SPONSORS


# ─── MBA/MASTER'S DETECTION ──────────────────────────────────────────────────

MBA_SIGNALS = [
    "mba preferred", "mba required", "mba or equivalent",
    "mba strongly preferred", "mba from top", "top-tier mba",
    "master's preferred", "master's required", "masters preferred",
    "masters required", "master's degree preferred",
    "graduate degree preferred", "advanced degree preferred",
    "advanced degree required", "graduate degree required",
    "mba or master", "mba/master",
]


def detect_mba_signal(text: str) -> bool:
    """Return True if the text contains MBA/Master's preference signals."""
    t = text.lower()
    return any(sig in t for sig in MBA_SIGNALS)


# ─── RESUME-CALIBRATED KEYWORD CLUSTERS ──────────────────────────────────────
# Derived from Dinesh Pant's 8 resume variants (Amadeus/Vertiv/Microsoft/Beats).
# 9 clusters aligned to target roles: PM, AI/ML PM, GTM, TPM, B2B, Data,
# Consulting, Travel, Leadership.
RESUME_CLUSTERS = {
    # ── 1. Core PM ───────────────────────────────────────────────────────────
    # Product management fundamentals that appear in target JDs
    "core_pm": [
        "product roadmap", "product strategy", "product vision", "product lifecycle",
        "product requirements", "PRD", "product spec", "feature prioritization",
        "user research", "customer discovery", "user stories", "backlog",
        "sprint planning", "agile", "scrum", "product launch", "product-market fit",
        "A/B testing", "experimentation", "product metrics", "product analytics",
        "OKR", "KPI", "go-to-market", "GTM", "product owner",
        "cross-functional", "stakeholder management",
    ],
    # ── 2. AI / ML ───────────────────────────────────────────────────────────
    # AI/ML domain expertise from Microsoft + AI-native company roles
    "ai_ml": [
        "machine learning", "artificial intelligence", "deep learning",
        "natural language processing", "NLP", "LLM", "large language model",
        "generative AI", "gen AI", "foundation model", "RAG",
        "retrieval augmented generation", "fine-tuning", "prompt engineering",
        "AI safety", "responsible AI", "model evaluation", "ML pipeline",
        "inference", "training data", "computer vision", "agentic AI",
        "AI platform", "model deployment", "vector database", "embeddings",
        "diffusion model", "multimodal", "AI governance",
    ],
    # ── 3. GTM & Strategy ────────────────────────────────────────────────────
    # Go-to-market and strategy keywords from Amadeus + consulting experience
    "gtm_strategy": [
        "go-to-market", "GTM strategy", "launch strategy", "market segmentation",
        "pricing strategy", "competitive analysis", "market entry", "expansion",
        "revenue strategy", "sales enablement", "partnerships", "growth strategy",
        "market analysis", "business development", "product positioning",
        "value proposition", "market sizing", "TAM", "SAM", "SOM",
        "win/loss analysis", "analyst relations", "category creation",
    ],
    # ── 4. Technical Depth ───────────────────────────────────────────────────
    # Engineering-adjacent skills from Vertiv (data center) + Microsoft (Azure)
    "technical_depth": [
        "API", "REST API", "GraphQL", "microservices", "system design",
        "scalability", "reliability", "SLA", "SLO", "CI/CD", "DevOps",
        "release management", "deployment", "technical spec", "architecture",
        "distributed systems", "cloud", "AWS", "Azure", "GCP",
        "Kubernetes", "Docker", "infrastructure", "technical debt",
        "capacity planning", "incident management", "observability",
        "monitoring", "data pipeline", "ETL", "integration",
    ],
    # ── 5. Enterprise B2B & SaaS ─────────────────────────────────────────────
    # B2B SaaS context from Amadeus (enterprise travel) + Microsoft (enterprise)
    "enterprise_b2b": [
        "B2B", "enterprise", "SaaS", "platform", "ARR", "MRR",
        "churn", "retention", "net revenue retention", "NRR",
        "customer success", "onboarding", "professional services",
        "multi-tenant", "self-serve", "PLG", "product-led growth",
        "account management", "renewal", "upsell", "expansion revenue",
        "enterprise sales", "solution selling", "RFP", "procurement",
        "SLA", "service delivery", "implementation", "customer journey",
    ],
    # ── 6. Data & Analytics ──────────────────────────────────────────────────
    # Quantitative skills across all resume variants
    "data_analytics": [
        "SQL", "Python", "Tableau", "Looker", "Power BI",
        "BigQuery", "Snowflake", "Redshift", "data-driven",
        "metrics", "dashboards", "data analysis", "analytics",
        "reporting", "business intelligence", "data modeling",
        "statistical analysis", "A/B testing", "cohort analysis",
        "funnel analysis", "attribution", "experimentation",
        "forecasting", "trend analysis", "KPI dashboard",
    ],
    # ── 7. Consulting & Transformation ───────────────────────────────────────
    # Consulting toolkit from MBA cases + Deloitte/McKinsey target roles
    "consulting_transformation": [
        "digital transformation", "change management", "process improvement",
        "business case", "stakeholder management", "client engagement",
        "client delivery", "client-facing", "workstream", "deliverable",
        "operating model", "target operating model", "capability assessment",
        "gap analysis", "maturity model", "current state", "future state",
        "advisory", "due diligence", "benchmarking", "ROI",
        "ERP", "SAP", "implementation", "proposal", "SOW",
        "project management", "PMO", "program governance",
    ],
    # ── 8. Travel & Domain ───────────────────────────────────────────────────
    # Amadeus + travel domain expertise (differentiator)
    "travel_domain": [
        "GDS", "NDC", "airline", "hospitality", "hotel",
        "booking", "reservation", "distribution", "travel tech",
        "OTA", "online travel", "travel management", "itinerary",
        "payments", "transactions", "billing", "invoicing",
        "fintech", "credit", "risk", "underwriting", "fraud",
        "KYC", "AML", "compliance", "supply chain", "logistics",
    ],
    # ── 9. Leadership & Soft Skills ──────────────────────────────────────────
    # Behavioral keywords from all resume variants
    "leadership_soft": [
        "cross-functional", "influence without authority", "executive",
        "stakeholder alignment", "consensus building", "alignment",
        "mentoring", "coaching", "team building", "leadership",
        "collaboration", "executive communication", "executive presence",
        "presentation skills", "executive summary", "C-suite",
        "board presentation", "organizational change", "ambiguity",
        "strategic thinking", "problem solving", "ownership",
        "bias for action", "customer obsession", "data-driven",
    ],
}

# Backwards-compatible alias used by load_keyword_clusters()
DEFAULT_CLUSTERS = RESUME_CLUSTERS


def load_keyword_clusters(path: str = None) -> dict:
    """Load keyword clusters from file or use defaults."""
    if path and os.path.exists(path):
        try:
            data = json.load(open(path))
            if isinstance(data, dict):
                clusters = {}
                for key, val in data.items():
                    if isinstance(val, list):
                        clusters[key] = [w.lower().strip() for w in val if w]
                    elif isinstance(val, dict) and "keywords" in val:
                        clusters[key] = [w.lower().strip() for w in val["keywords"] if w]
                if clusters:
                    return clusters
        except Exception as e:
            print(f"  ⚠️ Could not load {path}: {e}, using defaults")
    return DEFAULT_CLUSTERS


def score_job(job: dict, clusters: dict) -> tuple[float, dict, dict, bool]:
    """
    Score a single job against keyword clusters.

    Returns:
        (composite_score, keyword_hits, cluster_scores, mba_preferred)
        - composite_score: 0-100 float (includes MBA bonus if applicable)
        - keyword_hits: {cluster_name: [matched_keywords]}
        - cluster_scores: {cluster_name: 0-100 score}
        - mba_preferred: True if MBA signal detected in description
    """
    description = (job.get("description") or "").lower()
    title = (job.get("role_title") or "").lower()
    text = f"{title} {description}"

    if not text.strip():
        return 0.0, {}, {}, False

    # Detect MBA signal
    mba_preferred = detect_mba_signal(description)

    keyword_hits = {}
    cluster_scores = {}

    category = job.get("role_category", "")
    primary_clusters = _get_primary_clusters(category)

    for cluster_name, keywords in clusters.items():
        hits = []
        for kw in keywords:
            if len(kw) <= 4:
                if re.search(r'\b' + re.escape(kw) + r'\b', text, re.IGNORECASE):
                    hits.append(kw)
            else:
                if kw.lower() in text:
                    hits.append(kw)

        if hits:
            keyword_hits[cluster_name] = hits

        if keywords:
            raw = len(hits) / len(keywords) * 100
            weight = 1.5 if cluster_name in primary_clusters else 1.0
            cluster_scores[cluster_name] = round(min(raw * weight, 100), 1)

    # ── Composite score ──────────────────────────────────────────────────────
    if cluster_scores:
        primary_scores = [v for k, v in cluster_scores.items() if k in primary_clusters]
        other_scores = [v for k, v in cluster_scores.items() if k not in primary_clusters]
        kw_score = (
            (sum(primary_scores) / max(len(primary_scores), 1)) * 0.7 +
            (sum(other_scores) / max(len(other_scores), 1)) * 0.3
        ) if primary_scores else (
            sum(other_scores) / max(len(other_scores), 1)
        )
    else:
        kw_score = 0

    cat_score = 100 if category else 0
    visa_score = 100 if "Known" in (job.get("visa_sponsor") or "") else 30
    fresh_score = _freshness_score(job.get("posted_date"))

    composite = (
        kw_score * SCORE_WEIGHTS["keyword_match"] +
        cat_score * SCORE_WEIGHTS["category_fit"] +
        visa_score * SCORE_WEIGHTS["visa_sponsor"] +
        fresh_score * SCORE_WEIGHTS["freshness"]
    )

    # MBA bonus — flat +15 points, capped at 100
    if mba_preferred:
        composite = min(composite + SCORE_WEIGHTS["mba_bonus"], 100)

    return round(composite, 1), keyword_hits, cluster_scores, mba_preferred


def _get_primary_clusters(category: str) -> set:
    """Map role category to its primary keyword clusters (RESUME_CLUSTERS keys)."""
    mapping = {
        "AI/ML Product Manager":      {"core_pm", "ai_ml", "technical_depth",
                                        "data_analytics"},
        "Product Manager":             {"core_pm", "enterprise_b2b",
                                        "gtm_strategy", "leadership_soft"},
        "Product Marketing":           {"gtm_strategy", "enterprise_b2b",
                                        "data_analytics", "leadership_soft"},
        "Technical Program Manager":   {"technical_depth", "data_analytics",
                                        "leadership_soft", "enterprise_b2b"},
        "Strategy & Operations":       {"gtm_strategy", "enterprise_b2b",
                                        "data_analytics", "consulting_transformation"},
        "Finance & Strategy / FP&A":   {"data_analytics", "consulting_transformation",
                                        "enterprise_b2b"},
        "Consulting":                  {"consulting_transformation", "leadership_soft",
                                        "gtm_strategy", "enterprise_b2b"},
        "Customer Success":            {"enterprise_b2b", "leadership_soft",
                                        "data_analytics"},
        "Solutions / Pre-Sales":       {"enterprise_b2b", "technical_depth",
                                        "consulting_transformation", "gtm_strategy"},
    }
    return mapping.get(category, set())


def _freshness_score(posted_date: str) -> float:
    """Score based on how recent the posting is."""
    if not posted_date:
        return 30
    try:
        posted = datetime.strptime(posted_date, "%Y-%m-%d")
        days = (datetime.now() - posted).days
        if days <= 1:
            return 100
        elif days <= 3:
            return 80
        elif days <= 7:
            return 50
        elif days <= 14:
            return 20
        else:
            return 5
    except ValueError:
        return 30


def score_batch(jobs: list[dict], clusters: dict = None,
                keywords_path: str = None) -> list[dict]:
    """Score a batch of jobs. Returns jobs with score fields added."""
    if clusters is None:
        clusters = load_keyword_clusters(keywords_path)

    for job in jobs:
        score, hits, c_scores, mba = score_job(job, clusters)
        job["match_score"] = score
        job["keyword_hits"] = hits
        job["cluster_scores"] = c_scores
        job["mba_preferred"] = mba

    jobs.sort(key=lambda j: j.get("match_score", 0), reverse=True)
    return jobs
