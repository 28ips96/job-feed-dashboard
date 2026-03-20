"""
enrichment.py — Contact enrichment provider abstraction.

Usage:
    provider = get_provider("apollo")          # or "clay"
    data = provider.enrich(email="x@co.com", company="Stripe", name="John")

    result = {
        "email": "x@co.com",
        "phone": "+1...",
        "title": "Senior PM",
        "linkedin_url": "https://linkedin.com/in/...",
        "connection_degree": 2,
        "enrichment_data": {...raw response...},
        "enriched_via": "apollo",
    }

Add API keys to settings.json:
    {
        "apollo_api_key": "xxx",
        "clay_api_key": "yyy"
    }
"""
import json
import os
import time
from abc import ABC, abstractmethod
from pathlib import Path

SETTINGS_PATH = os.path.join(os.path.dirname(__file__), "settings.json")


def _load_settings() -> dict:
    if os.path.exists(SETTINGS_PATH):
        try:
            return json.loads(Path(SETTINGS_PATH).read_text())
        except Exception:
            pass
    return {}


def build_linkedin_urls(company: str, role_category: str = "", role_title: str = "") -> dict:
    """
    Build LinkedIn people-search URLs for a company.
    Returns dict with keys: alumni, recruiter, peers.

    URL format: company name is double-quoted (%22Company%22) so LinkedIn
    treats it as an exact-match filter. Degree params narrow to 1st/2nd.
    """
    qco = '%22' + company.replace(' ', '%20') + '%22'
    deg12 = '&network=%5B%22F%22%2C%22S%22%5D'
    deg1  = '&network=%5B%22F%22%5D'

    # Role keyword for recruiter search
    role_kw = _role_keywords(role_category, role_title)
    # Title keywords (2-3 meaningful words from title)
    title_kw = _title_keywords(role_title)

    base = "https://www.linkedin.com/search/results/people/?keywords="
    return {
        "alumni":    f"{base}{qco}+Indiana+University{deg12}",
        "recruiter": f"{base}{qco}+recruiter+{role_kw}{deg1}",
        "peers":     f"{base}{qco}+{title_kw}{deg12}",
    }


def _role_keywords(role_category: str, role_title: str) -> str:
    mapping = {
        "AI/ML Product Manager":      "recruiter+AI+product+manager",
        "Product Manager":            "recruiter+product+manager",
        "Product Marketing":          "recruiter+product+marketing",
        "Technical Program Manager":  "recruiter+program+manager",
        "Finance & Strategy / FP&A":  "recruiter+finance+FPA",
        "Consulting":                 "recruiter+consultant",
        "Strategy & Operations":      "recruiter+strategy+operations",
        "Customer Success":           "recruiter+customer+success",
        "Solutions / Pre-Sales":      "recruiter+solutions+consultant",
    }
    return mapping.get(role_category, "recruiter+product")


def _title_keywords(title: str) -> str:
    stop = {"senior", "sr", "jr", "lead", "the", "and", "or", "of", "a",
            "an", "manager", "specialist", "associate", "ii", "iii", "iv"}
    words = title.lower().replace("-", " ").replace(",", "").split()
    meaningful = [w for w in words if len(w) > 2 and w not in stop][:3]
    return "+".join(meaningful) or "product+manager"


# ─── ENRICHMENT PROVIDER ABSTRACTION ─────────────────────────────────────────

class EnrichmentProvider(ABC):
    """Base class for contact enrichment providers."""

    @abstractmethod
    def enrich(self, email: str = None, name: str = None,
               company: str = None, linkedin_url: str = None) -> dict:
        """
        Enrich a contact. Pass at least one identifier.
        Returns a dict with normalized fields + raw enrichment_data.
        """

    def _empty_result(self, via: str) -> dict:
        return {
            "email": None,
            "phone": None,
            "title": None,
            "linkedin_url": None,
            "connection_degree": None,
            "enrichment_data": {},
            "enriched_via": via,
        }


class ApolloProvider(EnrichmentProvider):
    """
    Apollo.io people enrichment.
    API docs: https://apolloio.github.io/apollo-api-docs/#people-enrichment

    Requires: settings.json → {"apollo_api_key": "..."}
    """

    ENDPOINT = "https://api.apollo.io/v1/people/match"

    def __init__(self, api_key: str = None):
        self.api_key = api_key or _load_settings().get("apollo_api_key", "")

    def enrich(self, email: str = None, name: str = None,
               company: str = None, linkedin_url: str = None) -> dict:
        if not self.api_key:
            raise ValueError("apollo_api_key not set in settings.json")

        try:
            import requests
        except ImportError:
            raise RuntimeError("requests library required: pip install requests")

        payload = {"api_key": self.api_key, "reveal_personal_emails": True}
        if email:
            payload["email"] = email
        if name:
            payload["name"] = name
        if company:
            payload["organization_name"] = company
        if linkedin_url:
            payload["linkedin_url"] = linkedin_url

        resp = requests.post(self.ENDPOINT, json=payload, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        person = data.get("person") or {}
        result = self._empty_result("apollo")
        result.update({
            "email": person.get("email"),
            "phone": (person.get("phone_numbers") or [{}])[0].get("raw_number"),
            "title": person.get("title"),
            "linkedin_url": person.get("linkedin_url"),
            "enrichment_data": person,
        })
        return result


class ClayProvider(EnrichmentProvider):
    """
    Clay.com enrichment via table webhook or HTTP API.
    Requires: settings.json → {"clay_api_key": "...", "clay_table_id": "..."}
    """

    ENDPOINT = "https://api.clay.com/v1/sources/http-api/webhook"

    def __init__(self, api_key: str = None, table_id: str = None):
        settings = _load_settings()
        self.api_key = api_key or settings.get("clay_api_key", "")
        self.table_id = table_id or settings.get("clay_table_id", "")

    def enrich(self, email: str = None, name: str = None,
               company: str = None, linkedin_url: str = None) -> dict:
        if not self.api_key:
            raise ValueError("clay_api_key not set in settings.json")

        try:
            import requests
        except ImportError:
            raise RuntimeError("requests library required: pip install requests")

        payload = {
            "email": email or "",
            "name": name or "",
            "company": company or "",
            "linkedin_url": linkedin_url or "",
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        resp = requests.post(
            f"{self.ENDPOINT}?table_id={self.table_id}",
            json=payload, headers=headers, timeout=20
        )
        resp.raise_for_status()
        data = resp.json()

        result = self._empty_result("clay")
        # Clay returns enriched row data; field names depend on your table schema
        result.update({
            "email": data.get("email") or email,
            "phone": data.get("phone"),
            "title": data.get("title"),
            "linkedin_url": data.get("linkedin_url") or linkedin_url,
            "enrichment_data": data,
        })
        return result


class NoopProvider(EnrichmentProvider):
    """Passthrough — no API key required. Used for testing / manual entry."""

    def enrich(self, email: str = None, name: str = None,
               company: str = None, linkedin_url: str = None) -> dict:
        return {
            "email": email,
            "phone": None,
            "title": None,
            "linkedin_url": linkedin_url,
            "connection_degree": None,
            "enrichment_data": {},
            "enriched_via": "manual",
        }


# ─── FACTORY ─────────────────────────────────────────────────────────────────

def get_provider(name: str = None) -> EnrichmentProvider:
    """
    Return the enrichment provider by name.
    Falls back to NoopProvider if name is None or API key is missing.

    Usage:
        p = get_provider()          # auto-detect from settings.json
        p = get_provider("apollo")
        p = get_provider("clay")
    """
    settings = _load_settings()
    if name is None:
        # Auto-detect: prefer Apollo if key present, then Clay, then Noop
        if settings.get("apollo_api_key"):
            name = "apollo"
        elif settings.get("clay_api_key"):
            name = "clay"
        else:
            name = "noop"

    if name == "apollo":
        return ApolloProvider()
    if name == "clay":
        return ClayProvider()
    return NoopProvider()
