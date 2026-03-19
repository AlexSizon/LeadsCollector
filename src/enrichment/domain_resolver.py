"""
Domain resolver utility.

Extracts and normalises root domains from raw URLs, handling
www/m/mobile subdomains and multi-part TLDs (e.g. .co.uk).
Provides helpers to detect known social and directory domains.
"""

from __future__ import annotations

from typing import Optional
from urllib.parse import urlparse

try:
    import tldextract as _tldextract
    _HAS_TLDEXTRACT = True
except ImportError:
    _HAS_TLDEXTRACT = False


# Known social / directory domain roots considered as non-owned web presence
SOCIAL_DOMAINS = frozenset({
    "instagram.com", "facebook.com", "fb.com",
    "twitter.com", "x.com",
    "tiktok.com",
    "linkedin.com",
    "youtube.com",
    "linktree.ee", "linktr.ee",
    "yelp.com", "tripadvisor.com",
    "google.com", "maps.google.com",
    "booking.com", "treatwell.co.uk", "treatwell.de",
    "fresha.com", "planity.com",
    "doctolib.fr", "doctolib.de",
    "jameda.de",
})

# Stripped subdomain prefixes (exact match against first label only)
_STRIP_PREFIXES = ("www.", "m.", "mobile.", "web.", "shop.")


def extract_root_domain(url: Optional[str]) -> Optional[str]:
    """Extract the root domain from a URL.

    Uses ``tldextract`` when available for accurate multi-part TLD
    handling (e.g. example.co.uk → example.co.uk). Falls back to a
    simple URL-parsing heuristic when the library is not installed.

    Parameters
    ----------
    url : Optional[str]
        Raw URL string. May or may not include a scheme.

    Returns
    -------
    Optional[str]
        Root domain string without subdomains (e.g. "smilestudio-berlin.de"),
        or None when the URL is empty or cannot be parsed.
    """
    if not url:
        return None
    # Ensure URL has a scheme so urlparse works correctly
    if not url.startswith(("http://", "https://", "//")):
        url = "https://" + url

    if _HAS_TLDEXTRACT:
        result = _tldextract.extract(url)
        if result.domain and result.suffix:
            return f"{result.domain}.{result.suffix}".lower()
        return None

    # Fallback: simple heuristic
    parsed = urlparse(url)
    host = parsed.netloc.lower().split(":")[0]  # strip port
    for prefix in _STRIP_PREFIXES:
        if host.startswith(prefix):
            host = host[len(prefix):]
            break
    parts = host.split(".")
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return host or None


def is_social_domain(url: Optional[str]) -> bool:
    """Return True if the URL resolves to a known social or directory domain."""
    if not url:
        return False
    domain = extract_root_domain(url)
    if not domain:
        return False
    return domain in SOCIAL_DOMAINS or any(url.lower().startswith(f"https://{d}") for d in SOCIAL_DOMAINS)
