"""
Normalization utilities for business metadata.

These helpers standardise phone numbers, company names and domains
across multiple data sources to aid deduplication and scoring.
"""

import re
from typing import Optional
from urllib.parse import urlparse

from ..enums import WebsiteStatus

try:
    import phonenumbers as _phonenumbers
    _HAS_PHONENUMBERS = True
except ImportError:
    _HAS_PHONENUMBERS = False


def normalize_phone(phone: Optional[str], default_region: str = "DE") -> Optional[str]:
    """Normalize a phone number to E.164 international format.

    Uses the ``phonenumbers`` library when available for accurate parsing;
    falls back to a simple digit-stripping heuristic otherwise.

    Returns None if the number cannot be normalised.
    """
    if not phone:
        return None
    if _HAS_PHONENUMBERS:
        try:
            parsed = _phonenumbers.parse(phone, default_region)
            if _phonenumbers.is_valid_number(parsed):
                return _phonenumbers.format_number(
                    parsed, _phonenumbers.PhoneNumberFormat.E164
                )
        except Exception:
            pass
    # Heuristic fallback
    digits = re.sub(r"\D", "", phone)
    return f"+{digits}" if digits else None


def normalize_name(name: str) -> str:
    """Return a lowercase, trimmed version of the company name for matching."""
    return re.sub(r"\s+", " ", name.strip().lower())


def extract_root_domain(url: Optional[str]) -> Optional[str]:
    """Extract the root domain from a URL (e.g. https://www.example.co.uk -> example.co.uk)."""
    if not url:
        return None
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    # Remove common subdomains
    for prefix in ["www.", "m.", "web."]:
        if host.startswith(prefix):
            host = host[len(prefix):]
            break
    # Return last two labels by default
    parts = host.split(".")
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return host


# Known social / directory domain roots (lower-case root domains)
_SOCIAL_ROOT_DOMAINS = frozenset({
    "instagram.com", "facebook.com", "fb.com",
    "twitter.com", "x.com",
    "tiktok.com",
    "linkedin.com",
    "youtube.com",
    "linktree.ee", "linktr.ee",
    "yelp.com", "tripadvisor.com",
    "google.com",
    "booking.com",
    "fresha.com", "planity.com",
    "doctolib.fr", "doctolib.de",
    "jameda.de",
    "treatwell.co.uk", "treatwell.de",
})


def classify_website_status(url: Optional[str]) -> Optional[WebsiteStatus]:
    """Classify a website URL as SOCIAL_ONLY or None (undetermined) before HTTP checks.

    Returns ``WebsiteStatus.NO_WEBSITE`` when url is empty/None.
    Returns ``WebsiteStatus.SOCIAL_ONLY`` when url resolves to a known social
    or directory domain.
    Returns ``None`` when the URL looks like a real owned domain that should
    be checked via HTTP.
    """
    if not url:
        return WebsiteStatus.NO_WEBSITE
    root = extract_root_domain(url)
    if root and root in _SOCIAL_ROOT_DOMAINS:
        return WebsiteStatus.SOCIAL_ONLY
    return None  # Needs HTTP check