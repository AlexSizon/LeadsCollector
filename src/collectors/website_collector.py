"""
Collector for business website presence detection.

Determines whether a website exists (and what kind), then optionally
delegates to the auditors for detailed issue detection.
"""

from __future__ import annotations

from typing import Optional, Tuple
from urllib.parse import urlparse

import requests

from ..enums import WebsiteStatus
from ..enrichment.normalizer import classify_website_status

# Phrases commonly found on parked / inactive domains
_PARKING_FINGERPRINTS = [
    "this domain is for sale",
    "domain for sale",
    "buy this domain",
    "sedo.com",
    "godaddy.com/domain",
    "dan.com",
    "underconstruction",
    "under construction",
    "coming soon",
    "website coming soon",
    "parked free",
    "blank parking page",
]


class WebsiteCollector:
    """Utility class for checking website status."""

    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers["User-Agent"] = (
            "Mozilla/5.0 (compatible; SMBLeadAgent/1.0)"
        )

    def check_website(self, url: Optional[str]) -> Tuple[WebsiteStatus, Optional[requests.Response]]:
        """Determine whether a website exists, is broken, social-only, etc.

        Returns
        -------
        Tuple[WebsiteStatus, Optional[requests.Response]]
            The status enum and the HTTP response (if successfully fetched),
            so callers can reuse the response for auditing without a second fetch.
        """
        # --- Pre-HTTP classification ---
        pre_status = classify_website_status(url)
        if pre_status is not None:
            return pre_status, None

        # --- HTTP fetch ---
        try:
            response = self._session.get(
                url,  # type: ignore[arg-type]
                timeout=self.timeout,
                allow_redirects=True,
            )
        except Exception:
            return WebsiteStatus.BROKEN_WEBSITE, None

        if response.status_code == 404:
            return WebsiteStatus.BROKEN_WEBSITE, response
        if response.status_code >= 500:
            return WebsiteStatus.BROKEN_WEBSITE, response
        if not (200 <= response.status_code < 400):
            return WebsiteStatus.UNKNOWN, response

        # --- Parking page detection ---
        content_lower = response.text.lower()
        if any(fp in content_lower for fp in _PARKING_FINGERPRINTS):
            return WebsiteStatus.BROKEN_WEBSITE, response

        return WebsiteStatus.HAS_WEBSITE, response