"""
Instagram discovery collector.

Uses Google site-search (`site:instagram.com`) to find Instagram business
profiles matching a niche × city query. For each candidate profile URL found
in the search results, optionally fetches the public Instagram page to extract
bio-level contact signals (phone, email, website link).

Design decision (D1): public HTML only, no authentication, no private API.
Falls back to an empty result list on any unrecoverable error so the main
pipeline is never interrupted.
"""

from __future__ import annotations

import logging
import random
import re
import time
from typing import List, Optional
from urllib.parse import quote_plus, urljoin, urlparse

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

# Regex to extract an Instagram handle from a profile URL
_IG_HANDLE_RE = re.compile(
    r"instagram\.com/([A-Za-z0-9_.]{1,30})/?(?:\?|$)", re.I
)

# Patterns to detect contact info inside Instagram bio / page HTML
_EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", re.I
)
_PHONE_RE = re.compile(
    r"(?:\+?\d[\d \(\)\-\.]{6,}\d)", re.I
)
_WEBSITE_RE = re.compile(
    r"https?://(?!(?:www\.)?instagram\.com)[^\s\"'>]{5,}", re.I
)

# Generic slugs that are platform pages, not business profiles
_GENERIC_SLUGS = frozenset({
    "p", "explore", "reels", "stories", "tv", "accounts",
    "login", "signup", "about", "help", "legal", "privacy",
    "hashtag", "directory", "press",
})

# How many profiles to attempt to fetch for bio data
_MAX_PROFILE_FETCHES = 3


# ---------------------------------------------------------------------------
# Collector class
# ---------------------------------------------------------------------------

class InstagramDiscoveryCollector:
    """Discover Instagram business profiles for a niche × city query."""

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
        """Return a list of SocialCandidates discovered on Instagram.

        Uses Google site-search to find Instagram profile URLs matching the
        query, then fetches the top profiles to extract bio-level data.
        Falls back to empty list on any error.
        """
        query = f'site:instagram.com "{niche}" "{city}"'
        log.debug("Instagram discovery search: %s", query)

        try:
            profile_urls = self._google_site_search(query, max_results)
        except Exception as exc:
            log.warning("Instagram discovery: Google search failed (%s)", exc)
            return []

        if not profile_urls:
            return []

        candidates: List[SocialCandidate] = []
        fetched = 0
        for url in profile_urls:
            handle = self._handle_from_url(url)
            if not handle or handle.lower() in _GENERIC_SLUGS:
                continue

            candidate = SocialCandidate(
                source_platform="instagram",
                handle_or_page_id=handle,
                display_name=handle.replace(".", " ").replace("_", " ").title(),
                city=city,
                country=country,
                niche=niche,
                social_urls={"instagram": f"https://www.instagram.com/{handle}/"},
            )

            # Attempt to fetch the profile page for richer bio data
            if fetched < _MAX_PROFILE_FETCHES:
                self._enrich_from_profile(candidate, url)
                fetched += 1
                self._sleep()

            candidates.append(candidate)
            if len(candidates) >= max_results:
                break

        log.info("Instagram discovery '%s' in '%s': %d candidates", niche, city, len(candidates))
        return candidates

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _google_site_search(self, query: str, max_results: int) -> List[str]:
        """Fetch Google search results and extract instagram.com profile URLs."""
        url = _GOOGLE_SEARCH_URL.format(query=quote_plus(query))
        headers = {"User-Agent": random.choice(_USER_AGENTS)}

        resp = self._request_with_backoff(url, headers=headers)
        if resp is None:
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        urls: List[str] = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            # Google wraps links in /url?q=...
            if "/url?q=" in href:
                href = href.split("/url?q=")[1].split("&")[0]
            if "instagram.com/" in href:
                # Clean up URL
                parsed = urlparse(href)
                clean = f"https://www.instagram.com{parsed.path}"
                if clean not in urls:
                    urls.append(clean)
            if len(urls) >= max_results:
                break

        return urls

    def _handle_from_url(self, url: str) -> Optional[str]:
        """Extract the Instagram handle from a profile URL."""
        m = _IG_HANDLE_RE.search(url)
        return m.group(1) if m else None

    def _enrich_from_profile(self, candidate: SocialCandidate, url: str) -> None:
        """Fetch the Instagram profile page and extract bio-level signals."""
        headers = {"User-Agent": random.choice(_USER_AGENTS)}
        resp = self._request_with_backoff(url, headers=headers)
        if resp is None:
            return

        text = resp.text

        # Display name from <title>
        soup = BeautifulSoup(text, "html.parser")
        title_tag = soup.find("title")
        if title_tag and title_tag.string:
            # Instagram titles are like "Name (@handle) • Instagram photos and videos"
            title_text = title_tag.string.split("•")[0].strip()
            if "(@" in title_text:
                display = title_text.split("(@")[0].strip()
                if display:
                    candidate.display_name = display

        # Extract bio text from meta description or og:description
        meta_desc = soup.find("meta", attrs={"name": "description"}) or \
                    soup.find("meta", attrs={"property": "og:description"})
        bio = ""
        if meta_desc and meta_desc.get("content"):
            bio = meta_desc["content"]
            candidate.raw_bio = bio

        # Email from bio
        if not candidate.email:
            m = _EMAIL_RE.search(bio)
            if m:
                email = m.group(0).lower()
                if not any(x in email for x in ("example.", "test.", ".png", ".jpg")):
                    candidate.email = email

        # Phone from bio
        if not candidate.phone:
            m = _PHONE_RE.search(bio)
            if m:
                phone = m.group(0).strip()
                if len(re.sub(r"\D", "", phone)) >= 7:
                    candidate.phone = phone

        # External website link from bio
        if not candidate.website_url:
            m = _WEBSITE_RE.search(bio)
            if m:
                candidate.website_url = m.group(0)

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
                        "Instagram discovery: request failed after 3 attempts (%s): %s",
                        url, exc,
                    )
                    return None
                log.debug(
                    "Instagram discovery: request error (%s), retry %d/3 in %ds",
                    exc, attempt, delay,
                )
                time.sleep(delay)
                delay *= 2
        return None

    def _sleep(self) -> None:
        """Sleep for the configured delay (with small jitter)."""
        jitter = random.uniform(-0.5, 0.5)
        time.sleep(max(0.0, self._delay + jitter))
