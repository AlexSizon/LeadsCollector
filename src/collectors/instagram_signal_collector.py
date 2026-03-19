"""
Collector module for extracting Instagram presence signals.

Strategy:
1. ``extract_handle_from_html()`` — find an Instagram handle linked from the
   business website (unauthenticated HTML parse, no scraping).
2. ``analyze_handle()`` — fetch the public Instagram profile page and classify
   the business maturity using observable HTML signals.

No Instagram Graph API or authentication is required.
"""

from __future__ import annotations

import re
from typing import Optional

import requests
from bs4 import BeautifulSoup

from ..enums import InstagramStatus

# Regex to extract an Instagram handle from a URL path
_HANDLE_RE = re.compile(
    r"instagram\.com/([A-Za-z0-9_.]{1,30})/?",
    re.IGNORECASE,
)

# User-Agent that mimics a common browser to reduce 403/blocking
_DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/121.0.0.0 Safari/537.36"
)


class InstagramSignalCollector:
    """Instagram signal checker using public, unauthenticated HTTP fetches."""

    PROFILE_URL_TEMPLATE = "https://www.instagram.com/{handle}/"

    def __init__(self, user_agent: Optional[str] = None):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent or _DEFAULT_UA})

    # ------------------------------------------------------------------
    # Handle discovery
    # ------------------------------------------------------------------

    def extract_handle_from_html(self, html: str) -> Optional[str]:
        """Extract an Instagram handle from page HTML.

        Looks for ``<a href>`` links pointing to instagram.com and
        extracts the first valid handle found.

        Parameters
        ----------
        html : str
            The website page HTML.

        Returns
        -------
        Optional[str]
            Instagram handle (no ``@``), or None if not found.
        """
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup.find_all("a", href=True):
            href = tag["href"]
            match = _HANDLE_RE.search(href)
            if match:
                handle = match.group(1).strip("/")
                # Exclude generic Instagram paths
                if handle.lower() not in {"p", "explore", "reel", "stories", "tv", ""}:
                    return handle
        return None

    # ------------------------------------------------------------------
    # Profile analysis
    # ------------------------------------------------------------------

    def analyze_handle(self, handle: str) -> InstagramStatus:
        """Classify an Instagram handle using public profile signals.

        Fetches the public profile page and inspects HTML for:
        - Profile existence (404 → NOT_FOUND)
        - Post count proxy (media count JSON embedded in page)
        - Bio link (external URL in profile)

        Returns
        -------
        InstagramStatus
        """
        url = self.PROFILE_URL_TEMPLATE.format(handle=handle)
        try:
            resp = self.session.get(url, timeout=12)
        except Exception:
            return InstagramStatus.UNKNOWN

        if resp.status_code == 404:
            return InstagramStatus.NOT_FOUND
        if resp.status_code >= 500:
            return InstagramStatus.UNKNOWN
        if resp.status_code == 429:
            # Rate-limited — cannot determine status
            return InstagramStatus.UNKNOWN

        html = resp.text

        # --- Detect active profile via JSON meta embedded in page ---
        # Instagram embeds shared data JSON that contains edge_owner_to_timeline_media.count
        post_count = self._extract_post_count(html)

        # --- Detect external link in bio ---
        link_in_bio = self._has_link_in_bio(html)

        if post_count is not None:
            if post_count >= 10 and link_in_bio:
                return InstagramStatus.FOUND_ACTIVE_WITH_LINK
            if post_count >= 10:
                return InstagramStatus.FOUND_ACTIVE
            if post_count > 0:
                return InstagramStatus.FOUND_INACTIVE
            # 0 posts
            return InstagramStatus.FOUND_INACTIVE

        # Fallback heuristics when post count not parseable
        active_signals = ("profilePic" in html or "ProfilePicture" in html)
        if active_signals and link_in_bio:
            return InstagramStatus.FOUND_ACTIVE_WITH_LINK
        if active_signals:
            return InstagramStatus.FOUND_ACTIVE

        return InstagramStatus.UNKNOWN

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_post_count(html: str) -> Optional[int]:
        """Try to extract a post count from Instagram's embedded page data."""
        # Pattern 1: JSON field in shared data
        m = re.search(r'"edge_owner_to_timeline_media"\s*:\s*\{\s*"count"\s*:\s*(\d+)', html)
        if m:
            return int(m.group(1))
        # Pattern 2: meta content "X Posts"
        m2 = re.search(r"(\d[\d,]*)\s+[Pp]osts?", html)
        if m2:
            return int(m2.group(1).replace(",", ""))
        return None

    @staticmethod
    def _has_link_in_bio(html: str) -> bool:
        """Detect an external link in the Instagram bio section."""
        # nofollow links in bio area
        return bool(re.search(r'rel="[^"]*nofollow[^"]*"', html))