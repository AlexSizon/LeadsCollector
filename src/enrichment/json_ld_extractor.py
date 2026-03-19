"""
JSON-LD / schema.org structured data extractor.

Parses ``<script type="application/ld+json">`` blocks from already-fetched
website HTML and extracts business-relevant fields without any additional
HTTP requests.

Returned dict keys
------------------
phone          : str | None
email          : str | None
name           : str | None
address        : str | None   (assembled from PostalAddress sub-fields)
opening_hours  : any | None   (raw value from JSON, string or list)
social_urls    : list[str]    (URLs from sameAs array matching known platforms)

When no LocalBusiness entity is found or all blocks are malformed, returns {}.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

_log = logging.getLogger(__name__)

# schema.org types ranked by specificity — higher index = more specific
# We prefer the most specific type when multiple entities are present.
_TYPE_PRIORITY: List[str] = [
    "organization",
    "localbusiness",
    "foodestablishment",
    "restaurant",
    "cafe",
    "coffeeshop",
    "bakery",
    "bar",
    "nightclub",
    "healthandbeautybusiness",
    "beautysalon",
    "hairsalon",
    "nailsalon",
    "spaorbeautysalon",
    "medicalorganization",
    "medicalbusiness",
    "dentist",
    "physician",
    "store",
    "automotivebusiness",
    "lodgingbusiness",
    "hotel",
    "tourisminformationcenter",
    "professionalservice",
    "accountingservice",
    "legalservice",
    "homeandconstructionbusiness",
]

# Social platform domain fragments used to classify sameAs URLs
_SOCIAL_DOMAINS = {
    "instagram.com": "instagram",
    "facebook.com": "facebook",
    "m.facebook.com": "facebook",
    "twitter.com": "twitter",
    "x.com": "twitter",
    "linkedin.com": "linkedin",
    "tiktok.com": "tiktok",
    "youtube.com": "youtube",
    "pinterest.com": "pinterest",
    "wa.me": "whatsapp",
}


def _type_rank(entity: dict) -> int:
    """Return the priority rank for a JSON-LD entity based on its @type."""
    raw_type = entity.get("@type", "")
    if isinstance(raw_type, list):
        types = [t.lower() for t in raw_type]
    else:
        types = [raw_type.lower()]
    best = -1
    for t in types:
        # Strip schema.org prefix if present
        t = t.replace("http://schema.org/", "").replace("https://schema.org/", "")
        if t in _TYPE_PRIORITY:
            best = max(best, _TYPE_PRIORITY.index(t))
    return best


def _is_local_business(entity: dict) -> bool:
    """Return True if the entity is a LocalBusiness or recognised subtype."""
    return _type_rank(entity) >= _TYPE_PRIORITY.index("localbusiness")


def _assemble_address(address_obj: Any) -> Optional[str]:
    """Build a human-readable address string from a PostalAddress object."""
    if isinstance(address_obj, str):
        return address_obj.strip() or None
    if not isinstance(address_obj, dict):
        return None
    parts = []
    street = address_obj.get("streetAddress", "").strip()
    locality = address_obj.get("addressLocality", "").strip()
    region = address_obj.get("addressRegion", "").strip()
    postal = address_obj.get("postalCode", "").strip()
    country = address_obj.get("addressCountry", "").strip()
    if street:
        parts.append(street)
    if locality:
        parts.append(locality)
    if region and region != locality:
        parts.append(region)
    if postal:
        parts.append(postal)
    if country:
        parts.append(country)
    return ", ".join(parts) if parts else None


def _classify_social_urls(same_as: Any) -> List[str]:
    """Return a list of recognised social profile URLs from a sameAs value."""
    if isinstance(same_as, str):
        urls = [same_as]
    elif isinstance(same_as, list):
        urls = [u for u in same_as if isinstance(u, str)]
    else:
        return []
    result = []
    for url in urls:
        lower = url.lower()
        for domain in _SOCIAL_DOMAINS:
            if domain in lower:
                result.append(url)
                break
    return result


def _extract_entity(entity: dict) -> Dict[str, Any]:
    """Extract fields from a single JSON-LD entity dict."""
    result: Dict[str, Any] = {
        "phone": None,
        "email": None,
        "name": None,
        "address": None,
        "opening_hours": None,
        "social_urls": [],
    }
    result["phone"] = entity.get("telephone") or entity.get("phone") or None
    result["email"] = entity.get("email") or None
    result["name"] = entity.get("name") or None
    result["address"] = _assemble_address(entity.get("address"))
    result["opening_hours"] = entity.get("openingHours") or entity.get("openingHoursSpecification") or None
    result["social_urls"] = _classify_social_urls(entity.get("sameAs", []))
    # Strip None values from phone/email
    if result["phone"] and not isinstance(result["phone"], str):
        result["phone"] = str(result["phone"])
    if result["email"] and not isinstance(result["email"], str):
        result["email"] = str(result["email"])
    return result


def extract_from_html(html: str) -> Dict[str, Any]:
    """Parse all JSON-LD blocks in HTML and return business-relevant fields.

    Searches for ``<script type="application/ld+json">`` elements, parses
    each one, picks the most specific LocalBusiness entity by type rank,
    and returns a dict with extracted fields.

    Returns an empty dict ``{}`` when:
    - No JSON-LD blocks are present
    - No blocks parse successfully
    - No LocalBusiness or recognised subtype entity is found

    This function operates entirely on provided HTML — no HTTP requests.
    """
    if not html:
        return {}

    soup = BeautifulSoup(html, "html.parser")
    scripts = soup.find_all("script", type="application/ld+json")
    if not scripts:
        return {}

    best_entity: Optional[dict] = None
    best_rank = -1

    for script in scripts:
        raw = (script.string or "").strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError) as exc:
            _log.debug("Skipping malformed JSON-LD block: %s", exc)
            continue

        # Handle @graph arrays
        candidates: List[dict] = []
        if isinstance(data, list):
            candidates = [e for e in data if isinstance(e, dict)]
        elif isinstance(data, dict):
            graph = data.get("@graph")
            if isinstance(graph, list):
                candidates = [e for e in graph if isinstance(e, dict)]
            else:
                candidates = [data]

        for entity in candidates:
            if not _is_local_business(entity):
                continue
            rank = _type_rank(entity)
            if rank > best_rank:
                best_rank = rank
                best_entity = entity

    if best_entity is None:
        return {}

    return _extract_entity(best_entity)
