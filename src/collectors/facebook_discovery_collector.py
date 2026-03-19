"""
Facebook discovery collector.

Uses Google site-search (`site:facebook.com`) to find Facebook business pages
matching a niche × city query. For each candidate page URL found in the search
results, optionally fetches the public Facebook page to extract visible contact
signals (phone, email, website link, about text).

Design decision (D1): public HTML only, no authentication, no Graph API.
Falls back to an empty result list on any unrecoverable error.
"""

from __future__ import annotations

import logging
import random
import re
import time
from typing import List, Optional
from urllib.parse import quote_plus, urlparse

import requests
from bs4 import BeautifulSoup

from ..models import SocialCandidate

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_GOOGLE_SEARCH_URL = "https://www.google.com/search?q={query}&num=10"

_USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:122.0) Gecko/20100101 Firefox/122.0",
]

# Regex to extract a Facebook page slug from a URL
_FB_SLUG_RE = re.compile(
    r"facebook\.com/(?:pages/[^/]+/)?([A-Za-z0-9._\-]{1,80})/?(?:\?|$)",
    re.I,
)

_EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", re.I
)
_PHONE_RE = re.compile(r"(?:\+?\d[\d \(\)\-\.]{6,}\d)", re.I)
_WEBSITE_RE = re.compile(
    r"https?://(?!(?:www\.)?facebook\.com)[^\s\"'>]{5,}", re.I
)

# Facebook platform slugs that are not business pages
_GENERIC_SLUGS = frozenset({
    "pg", "pages", "groups", "events", "marketplace", "watch",
    "gaming", "ads", "business", "help", "legal", "privacy",
    "login", "signup", "share", "sharer", "dialog", "photo",
    "video", "profile.php", "home.php", "people", "places",
})

_MAX_PROFILE_FETCHES = 3


# ---------------------------------------------------------------------------
# Collector class
# ---------------------------------------------------------------------------

class FacebookDiscoveryCollector:
    """Discover Facebook business pages for a niche × city query."""

    def __init__(self, request_delay: float = 3.0, timeout: int = 10) -> None:
        self._delay = request_delay
        self._timeout = timeout
        self._session = requests.Session()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def search(
        self,
        niche: str,
        city: str,
        country: str = "",
        max_results: int = 10,
    ) -> List[SocialCandidate]:
        """Return a list of SocialCandidates discovered on Facebook.

        Uses Google site-search to find Facebook page URLs, then fetches
        the top pages to extract visible contact information.
        Falls back to empty list on any error.
        """
        query = f'site:facebook.com "{niche}" "{city}"'
        log.debug("Facebook discovery search: %s", query)

        try:
            page_urls = self._google_site_search(query, max_results)
        except Exception as exc:
            log.warning("Facebook discovery: Google search failed (%s)", exc)
            return []

        if not page_urls:
            return []

        candidates: List[SocialCandidate] = []
        fetched = 0
        for url in page_urls:
            slug = self._slug_from_url(url)
            if not slug or slug.lower() in _GENERIC_SLUGS:
                continue

            candidate = SocialCandidate(
                source_platform="facebook",
                handle_or_page_id=slug,
                display_name=slug.replace("-", " ").replace(".", " ").replace("_", " ").title(),
                city=city,
                country=country,
                niche=niche,
                social_urls={"facebook": f"https://www.facebook.com/{slug}"},
            )

            if fetched < _MAX_PROFILE_FETCHES:
                self._enrich_from_page(candidate, url)
                fetched += 1
                self._sleep()

            candidates.append(candidate)
            if len(candidates) >= max_results:
                break

        log.info(
            "Facebook discovery '%s' in '%s': %d candidates",
            niche, city, len(candidates),
        )
        return candidates

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _google_site_search(self, query: str, max_results: int) -> List[str]:
        """Fetch Google search results and extract facebook.com page URLs."""
        url = _GOOGLE_SEARCH_URL.format(query=quote_plus(query))
        headers = {"User-Agent": random.choice(_USER_AGENTS)}

        resp = self._request_with_backoff(url, headers=headers)
        if resp is None:
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        urls: List[str] = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/url?q=" in href:
                href = href.split("/url?q=")[1].split("&")[0]
            if "facebook.com/" in href and "facebook.com/l.php" not in href:
                parsed = urlparse(href)
                clean = f"https://www.facebook.com{parsed.path.rstrip('/')}"
                if clean not in urls:
                    urls.append(clean)
            if len(urls) >= max_results:
                break

        return urls

    def _slug_from_url(self, url: str) -> Optional[str]:
        """Extract the Facebook page slug from a URL."""
        m = _FB_SLUG_RE.search(url)
        return m.group(1) if m else None

    def _enrich_from_page(self, candidate: SocialCandidate, url: str) -> None:
        """Fetch the Facebook page and extract visible contact signals."""
        headers = {"User-Agent": random.choice(_USER_AGENTS)}
        resp = self._request_with_backoff(url, headers=headers)
        if resp is None:
            return

        text = resp.text
        soup = BeautifulSoup(text, "html.parser")

        # Display name from <title>
        title_tag = soup.find("title")
        if title_tag and title_tag.string:
            title_clean = title_tag.string.split("|")[0].split("-")[0].strip()
            if title_clean:
                candidate.display_name = title_clean

        # og:description for about/bio text
        og_desc = soup.find("meta", attrs={"property": "og:description"})
        about = ""
        if og_desc and og_desc.get("content"):
            about = og_desc["content"]
            candidate.raw_bio = about

        # Email
        if not candidate.email:
            m = _EMAIL_RE.search(text)
            if m:
                email = m.group(0).lower()
                if not any(x in email for x in ("example.", "test.", ".png", ".jpg")):
                    candidate.email = email

        # Phone
        if not candidate.phone:
            m = _PHONE_RE.search(about)
            if m:
                phone = m.group(0).strip()
                if len(re.sub(r"\D", "", phone)) >= 7:
                    candidate.phone = phone

        # Website link  
        if not candidate.website_url:
            m = _WEBSITE_RE.search(text)
            if m:
                candidate.website_url = m.group(0)

        # Linked Instagram
        ig_re = re.compile(r"instagram\.com/([A-Za-z0-9_.]{1,30})", re.I)
        ig_m = ig_re.search(text)
        if ig_m:
            handle = ig_m.group(1)
            candidate.social_urls["instagram"] = (
                f"https://www.instagram.com/{handle}/"
            )

    def _request_with_backoff(
        self,
        url: str,
        headers: Optional[dict] = None,
    ) -> Optional[requests.Response]:
        """GET url with up to 3 retries and exponential backoff."""
        delay = 10
        for attempt in range(1, 4):
            try:
                resp = self._session.get(
                    url, headers=headers, timeout=self._timeout
                )
                resp.raise_for_status()
                return resp
            except requests.RequestException as exc:
                if attempt == 3:
                    log.warning(
                        "Facebook discovery: request failed after 3 attempts (%s): %s",
                        url, exc,
                    )
                    return None
                log.debug(
                    "Facebook discovery: request error (%s), retry %d/3 in %ds",
                    exc, attempt, delay,
                )
                time.sleep(delay)
                delay *= 2
        return None

    def _sleep(self) -> None:
        """Sleep for the configured delay (with small jitter)."""
        jitter = random.uniform(-0.5, 0.5)
        time.sleep(max(0.0, self._delay + jitter))
