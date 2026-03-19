"""
TripAdvisor discovery collector.

Uses Google site-search (``site:tripadvisor.com``) to find business
listings on TripAdvisor matching a hospitality niche × city query.
For each candidate listing URL found, optionally fetches the public
TripAdvisor page to extract phone and website URL signals.

Scope: only runs for hospitality niches (restaurant, café, bar, bakery).
Non-hospitality queries immediately return an empty list so the pipeline
incurs no unnecessary HTTP overhead.

Design decision (D1): same Google site-search pattern as Instagram
and Facebook discovery collectors — avoids direct TripAdvisor scraping
and the associated bot-detection risk.
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

# Niches for which TripAdvisor is relevant
HOSPITALITY_NICHES: frozenset = frozenset({
    "restaurant",
    "café",
    "café-bar",
    "bar",
    "bakery",
})

_GOOGLE_SEARCH_URL = "https://www.google.com/search?q={query}&num=10"

_USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:122.0) Gecko/20100101 Firefox/122.0",
]

# Regex patterns for extracting contact data from listing pages
_PHONE_RE = re.compile(
    r"(?:tel:|callto:)?(\+?\d[\d \(\)\-\.]{6,}\d)", re.I
)
_WEBSITE_RE = re.compile(
    r"https?://(?!(?:www\.)?tripadvisor\.)[^\s\"'<>]{5,}", re.I
)

# How many listing pages to fetch for richer data
_MAX_LISTING_FETCHES = 3


# ---------------------------------------------------------------------------
# Collector class
# ---------------------------------------------------------------------------

class TripAdvisorCollector:
    """Discover TripAdvisor listings for a hospitality niche × city query."""

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
        """Return a list of SocialCandidates discovered on TripAdvisor.

        Returns an empty list immediately for non-hospitality niches.
        Falls back to empty list on any unrecoverable error.
        """
        # Guard: only run for hospitality niches (D5)
        if niche.lower() not in HOSPITALITY_NICHES:
            return []

        query = f'site:tripadvisor.com "{niche}" "{city}"'
        log.debug("TripAdvisor discovery search: %s", query)

        try:
            listing_urls = self._google_site_search(query, max_results)
        except Exception as exc:
            log.warning(
                "TripAdvisor discovery: Google search failed for %s / %s — %s",
                niche, city, exc,
            )
            return []

        if not listing_urls:
            return []

        candidates: List[SocialCandidate] = []
        fetched = 0

        for url in listing_urls:
            display_name = self._name_from_url(url)
            candidate = SocialCandidate(
                source_platform="tripadvisor",
                handle_or_page_id=url,
                display_name=display_name or f"{niche.title()} in {city}",
                city=city,
                country=country,
                niche=niche,
                social_urls={},
            )

            # Attempt to fetch the listing page for richer data
            if fetched < _MAX_LISTING_FETCHES:
                self._enrich_from_listing(candidate, url)
                fetched += 1
                self._sleep()

            candidates.append(candidate)
            if len(candidates) >= max_results:
                break

        log.info(
            "TripAdvisor discovery '%s' in '%s': %d candidates",
            niche, city, len(candidates),
        )
        return candidates

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _google_site_search(self, query: str, max_results: int) -> List[str]:
        """Fetch Google search results and extract tripadvisor.com listing URLs."""
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
            if "tripadvisor." in href and "/Restaurant_Review" in href or \
               "tripadvisor." in href and "/Attraction_Review" in href or \
               "tripadvisor." in href and "/-d" in href:
                parsed = urlparse(href)
                clean = f"https://www.tripadvisor.com{parsed.path}"
                if clean not in urls:
                    urls.append(clean)
            if len(urls) >= max_results:
                break

        return urls

    @staticmethod
    def _name_from_url(url: str) -> Optional[str]:
        """Attempt to extract a business name from a TripAdvisor listing URL path."""
        # TripAdvisor URLs look like: /Restaurant_Review-g123-d456-Reviews-Business_Name-City.html
        path = urlparse(url).path
        # Try to extract the business name segment
        m = re.search(r"-Reviews-(.+?)(?:-\w+)?\.html", path)
        if m:
            raw = m.group(1).replace("_", " ").replace("-", " ").strip()
            return raw.title() if raw else None
        return None

    def _enrich_from_listing(self, candidate: SocialCandidate, url: str) -> None:
        """Fetch the TripAdvisor listing page and extract phone + website URL."""
        headers = {"User-Agent": random.choice(_USER_AGENTS)}
        resp = self._request_with_backoff(url, headers=headers)
        if resp is None:
            return

        text = resp.text
        soup = BeautifulSoup(text, "html.parser")

        # ── Business name from <title> ───────────────────────────────
        title_tag = soup.find("title")
        if title_tag and title_tag.string:
            # Titles are like "Business Name - City Restaurant Reviews"
            title_text = title_tag.string.split(" - ")[0].strip()
            if title_text:
                candidate.display_name = title_text

        # ── Phone from tel: links in the page ───────────────────────
        if not candidate.phone:
            tel_links = soup.find_all("a", href=re.compile(r"^tel:", re.I))
            for link in tel_links:
                phone_raw = link["href"].replace("tel:", "").strip()
                if phone_raw:
                    candidate.phone = phone_raw
                    break
            # Fallback: scan visible text for phone-like patterns
            if not candidate.phone:
                m = _PHONE_RE.search(text)
                if m:
                    phone_raw = m.group(1).strip()
                    if len(re.sub(r"\D", "", phone_raw)) >= 7:
                        candidate.phone = phone_raw

        # ── Website URL from external link buttons ───────────────────
        if not candidate.website_url:
            m = _WEBSITE_RE.search(text)
            if m:
                candidate.website_url = m.group(0)

    def _request_with_backoff(
        self,
        url: str,
        headers: Optional[dict] = None,
    ) -> Optional[requests.Response]:
        """GET *url* with up to 3 retries and exponential backoff (10 → 20 → 40 s)."""
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
                        "TripAdvisor discovery: request failed after 3 attempts (%s): %s",
                        url, exc,
                    )
                    return None
                log.debug(
                    "TripAdvisor discovery: request error (%s), retry %d/3 in %ds",
                    exc, attempt, delay,
                )
                time.sleep(delay)
                delay *= 2
        return None

    def _sleep(self) -> None:
        """Sleep for the configured delay (with small jitter)."""
        jitter = random.uniform(-0.5, 0.5)
        time.sleep(max(0.0, self._delay + jitter))
