"""
Social presence collector.

Extracts email addresses and social media profile URLs from:
1. Website HTML (regex + link parsing)
2. OSM ``contact:*`` / plain tag dict already fetched by OverpassCollector

Supported platforms:
    email, facebook, twitter / x, instagram, tiktok,
    linkedin, youtube, pinterest, whatsapp, telegram
"""

from __future__ import annotations

import re
from typing import Dict, Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
    re.IGNORECASE,
)

# Per-platform URL fragment patterns — ordered by specificity
_SOCIAL_PATTERNS: Dict[str, re.Pattern] = {
    "facebook":  re.compile(r"(?:https?://)?(?:www\.)?facebook\.com/([A-Za-z0-9_.%-]+)", re.I),
    "twitter":   re.compile(r"(?:https?://)?(?:www\.)?(?:twitter|x)\.com/([A-Za-z0-9_.%-]+)", re.I),
    "instagram": re.compile(r"(?:https?://)?(?:www\.)?instagram\.com/([A-Za-z0-9_.%-]+)", re.I),
    "tiktok":    re.compile(r"(?:https?://)?(?:www\.)?tiktok\.com/@?([A-Za-z0-9_.%-]+)", re.I),
    "linkedin":  re.compile(r"(?:https?://)?(?:www\.)?linkedin\.com/(?:company|in)/([A-Za-z0-9_.%-]+)", re.I),
    "youtube":   re.compile(r"(?:https?://)?(?:www\.)?youtube\.com/(?:channel/|c/|user/|@)([A-Za-z0-9_.\-]+)", re.I),
    "pinterest": re.compile(r"(?:https?://)?(?:www\.)?pinterest\.(?:com|es|co\.uk|de|fr)/([A-Za-z0-9_.%-]+)", re.I),
    "whatsapp":  re.compile(r"(?:https?://)?(?:wa\.me|api\.whatsapp\.com/send|web\.whatsapp\.com|chat\.whatsapp\.com)/\+?([0-9+%]+)", re.I),
    "telegram":  re.compile(r"(?:https?://)?(?:t\.me|telegram\.(?:me|org))/([A-Za-z0-9_]+)", re.I),
}

# OSM tag names that may carry social / contact info
_OSM_TAG_MAP: Dict[str, list[str]] = {
    "email":     ["email", "contact:email"],
    "facebook":  ["contact:facebook", "facebook"],
    "twitter":   ["contact:twitter", "twitter"],
    "instagram": ["contact:instagram", "instagram"],
    "tiktok":    ["contact:tiktok", "tiktok"],
    "linkedin":  ["contact:linkedin", "linkedin"],
    "youtube":   ["contact:youtube", "youtube"],
    "pinterest": ["contact:pinterest", "pinterest"],
    "whatsapp":  ["contact:whatsapp", "whatsapp"],
    "telegram":  ["contact:telegram", "telegram"],
}

# Paths / slugs that are generic platform pages, not profiles
_GENERIC_SLUGS = frozenset({
    "home", "about", "login", "signup", "register", "help", "support",
    "terms", "privacy", "legal", "ads", "business", "developers",
    "explore", "trending", "discover", "search", "hashtag", "reel",
    "stories", "watch", "feed", "p", "tv", "sharer", "share",
    "pages", "events", "groups", "marketplace",
})


# ---------------------------------------------------------------------------
# Public collector
# ---------------------------------------------------------------------------

class SocialCollector:
    """Extract email and social media signals from HTML or OSM tag dicts."""

    # ------------------------------------------------------------------
    # HTML extraction
    # ------------------------------------------------------------------

    def extract_from_html(self, html: str, base_url: str = "") -> Dict[str, Optional[str]]:
        """Parse an HTML page and extract email + social profile URLs.

        Returns a dict with keys: email, facebook, twitter, instagram,
        tiktok, linkedin, youtube, pinterest, whatsapp, telegram.
        Values are full canonical URLs (or just the email string).
        Missing entries have value ``None``.
        """
        result: Dict[str, Optional[str]] = {k: None for k in _SOCIAL_PATTERNS}
        result["email"] = None

        if not html:
            return result

        soup = BeautifulSoup(html, "html.parser")

        # ── Email ───────────────────────────────────────────────────────
        # 1. mailto: links (most reliable)
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith("mailto:"):
                addr = href[7:].split("?")[0].strip()
                if addr and "@" in addr:
                    result["email"] = addr
                    break

        # 2. Regex across visible text + selected meta tags
        if result["email"] is None:
            page_text = html
            emails = _EMAIL_RE.findall(page_text)
            for em in emails:
                # Exclude common false-positives
                if not any(em.endswith(s) for s in (".png", ".jpg", ".svg", ".gif", ".css", ".js")):
                    dom = em.split("@")[1].lower()
                    if not any(x in dom for x in ("example.", "test.", "domain.", "yourdomain.", "email.")):
                        result["email"] = em
                        break

        # ── Social links ────────────────────────────────────────────────
        # Collect all <a href> and <link rel> values
        candidate_urls: list[str] = []
        for tag in soup.find_all(["a", "link"], href=True):
            candidate_urls.append(tag["href"])
        # Also meta og:url / twitter:site
        for meta in soup.find_all("meta"):
            content = meta.get("content", "")
            if content and ("facebook.com" in content or "twitter.com" in content
                            or "instagram.com" in content or "tiktok.com" in content
                            or "linkedin.com" in content or "youtube.com" in content):
                candidate_urls.append(content)

        for url in candidate_urls:
            # Resolve relative URLs
            if base_url and not url.startswith("http"):
                url = urljoin(base_url, url)

            for platform, pattern in _SOCIAL_PATTERNS.items():
                if result[platform] is not None:
                    continue
                m = pattern.search(url)
                if m:
                    slug = m.group(1).rstrip("/").lower()
                    if slug not in _GENERIC_SLUGS and len(slug) >= 2:
                        # Normalise to canonical URL
                        result[platform] = _normalise_url(platform, slug, url)
                        break

        return result

    # ------------------------------------------------------------------
    # OSM tag extraction
    # ------------------------------------------------------------------

    @staticmethod
    def extract_from_osm_tags(tags: Dict[str, str]) -> Dict[str, Optional[str]]:
        """Pull social / contact info directly from OSM tags dict.

        Returns same structure as :meth:`extract_from_html`.
        """
        result: Dict[str, Optional[str]] = {k: None for k in _SOCIAL_PATTERNS}
        result["email"] = None

        for field_name, tag_candidates in _OSM_TAG_MAP.items():
            for tag_key in tag_candidates:
                val = tags.get(tag_key, "").strip()
                if val:
                    if field_name == "email":
                        result["email"] = val
                    else:
                        # If OSM value is already a full URL, keep it; else try
                        # to match with the platform pattern and normalise
                        m = _SOCIAL_PATTERNS[field_name].search(val)
                        if m:
                            slug = m.group(1).rstrip("/")
                            result[field_name] = _normalise_url(field_name, slug, val)
                        elif val.startswith("http"):
                            result[field_name] = val
                        else:
                            # Bare username / handle
                            result[field_name] = _normalise_url(field_name, val, "")
                    break  # first matching tag wins

        return result

    # ------------------------------------------------------------------
    # Merge
    # ------------------------------------------------------------------

    @staticmethod
    def merge(html_result: Dict, osm_result: Dict) -> Dict[str, Optional[str]]:
        """Merge HTML-extracted and OSM-extracted results.

        OSM values win for fields where both exist and differ,
        because OSM data was entered by the business owner.
        HTML values fill in gaps not present in OSM.
        """
        merged: Dict[str, Optional[str]] = {}
        for key in html_result:
            merged[key] = osm_result.get(key) or html_result.get(key)
        return merged


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalise_url(platform: str, slug: str, original: str) -> str:
    """Build a canonical profile URL from a platform slug."""
    slug = slug.rstrip("/")
    templates: Dict[str, str] = {
        "facebook":  "https://www.facebook.com/{slug}",
        "twitter":   "https://twitter.com/{slug}",
        "instagram": "https://www.instagram.com/{slug}/",
        "tiktok":    "https://www.tiktok.com/@{slug}",
        "linkedin":  "https://www.linkedin.com/company/{slug}",
        "youtube":   "https://www.youtube.com/@{slug}",
        "pinterest": "https://www.pinterest.com/{slug}",
        "whatsapp":  "https://wa.me/{slug}",
        "telegram":  "https://t.me/{slug}",
    }
    if platform in templates:
        return templates[platform].format(slug=slug)
    # Fallback: return original URL if it starts with http
    return original if original.startswith("http") else f"https://{original}"
