"""
Cross-source matcher.

Matches SocialCandidate objects discovered from Instagram/Facebook against
existing BusinessLead records using multi-signal confidence scoring.

Confidence levels (design D3):
  HIGH     — name similarity >= 0.85 AND (phone OR domain OR social URL match)
  MEDIUM   — name similarity >= 0.70 AND city match
  LOW      — name similarity >= 0.55 AND city match
  UNMATCHED — below LOW threshold
"""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from typing import List, Optional
from urllib.parse import urlparse

from ..models import BusinessLead, MatchResult, SocialCandidate
from ..enums import MatchConfidence, SocialPresenceStatus


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _normalise_name(name: str) -> str:
    """Lowercase, strip accents, remove punctuation, collapse whitespace."""
    # NFKD decomposition → remove combining characters
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_name = "".join(c for c in nfkd if not unicodedata.combining(c))
    # Remove non-alphanumeric except spaces
    cleaned = re.sub(r"[^a-z0-9 ]", " ", ascii_name.lower())
    return " ".join(cleaned.split())


def _name_similarity(a: str, b: str) -> float:
    """Return SequenceMatcher ratio between two normalised names (0.0–1.0)."""
    na, nb = _normalise_name(a), _normalise_name(b)
    if not na or not nb:
        return 0.0
    return SequenceMatcher(None, na, nb).ratio()


def _extract_domain(url: Optional[str]) -> Optional[str]:
    """Return the registered domain (without www.) from a URL, or None."""
    if not url:
        return None
    try:
        parsed = urlparse(url if "://" in url else f"https://{url}")
        host = parsed.netloc or parsed.path
        host = host.lower().strip()
        # Strip port
        host = host.split(":")[0]
        # Strip www.
        if host.startswith("www."):
            host = host[4:]
        return host or None
    except Exception:
        return None


def _normalise_phone(phone: Optional[str]) -> Optional[str]:
    """Strip non-digit characters for comparison."""
    if not phone:
        return None
    digits = re.sub(r"\D", "", phone)
    return digits[-9:] if len(digits) >= 9 else (digits or None)


# ---------------------------------------------------------------------------
# Main matcher class
# ---------------------------------------------------------------------------

class CrossSourceMatcher:
    """Match SocialCandidates against a list of BusinessLeads."""

    def match(
        self,
        candidate: SocialCandidate,
        leads: List[BusinessLead],
    ) -> MatchResult:
        """Score ``candidate`` against every lead and return the best match.

        Returns a MatchResult with the appropriate confidence level and the
        index of the best matching lead (or None if UNMATCHED).
        """
        best_idx: Optional[int] = None
        best_confidence = MatchConfidence.UNMATCHED
        best_sim = 0.0

        cand_domain = _extract_domain(candidate.website_url)
        cand_phone = _normalise_phone(candidate.phone)
        cand_social_domains = {
            _extract_domain(u)
            for u in candidate.social_urls.values()
            if u
        } - {None}

        for idx, lead in enumerate(leads):
            # Skip leads from a completely different city
            if candidate.city and lead.city:
                if _normalise_name(candidate.city) != _normalise_name(lead.city):
                    continue

            sim = _name_similarity(candidate.display_name, lead.company_name)
            if sim < 0.55:
                continue

            # Build secondary signal flags
            phone_match = bool(
                cand_phone
                and _normalise_phone(lead.phone) == cand_phone
            )
            lead_domain = _extract_domain(lead.website_url)
            domain_match = bool(
                cand_domain
                and lead_domain
                and cand_domain == lead_domain
            )
            # Check if lead's own social URLs overlap with candidate
            lead_social_domains = set()
            for attr in (
                "facebook_url", "twitter_url", "instagram_url",
                "tiktok_url", "linkedin_url",
            ):
                val = getattr(lead, attr, None)
                d = _extract_domain(val)
                if d:
                    lead_social_domains.add(d)
            social_match = bool(cand_social_domains & lead_social_domains)

            # Determine confidence
            if sim >= 0.85 and (phone_match or domain_match or social_match):
                confidence = MatchConfidence.HIGH
            elif sim >= 0.70:
                confidence = MatchConfidence.MEDIUM
            else:
                confidence = MatchConfidence.LOW

            # Keep best match (prefer higher confidence, then higher sim)
            conf_rank = {
                MatchConfidence.HIGH: 3,
                MatchConfidence.MEDIUM: 2,
                MatchConfidence.LOW: 1,
                MatchConfidence.UNMATCHED: 0,
            }
            if conf_rank[confidence] > conf_rank[best_confidence] or (
                confidence == best_confidence and sim > best_sim
            ):
                best_idx = idx
                best_confidence = confidence
                best_sim = sim

        return MatchResult(confidence=best_confidence, matched_index=best_idx)

    def merge_into(
        self,
        candidate: SocialCandidate,
        lead: BusinessLead,
    ) -> None:
        """Merge candidate's social data into ``lead``.

        Only fills empty (None / empty-list) fields — never overwrites
        existing non-null values.
        """
        _SOCIAL_ATTR_MAP = {
            "facebook":  "facebook_url",
            "twitter":   "twitter_url",
            "instagram": "instagram_url",
            "tiktok":    "tiktok_url",
            "linkedin":  "linkedin_url",
            "youtube":   "youtube_url",
            "pinterest": "pinterest_url",
            "whatsapp":  "whatsapp_url",
            "telegram":  "telegram_url",
        }
        _downgradable = {SocialPresenceStatus.UNKNOWN, SocialPresenceStatus.NOT_FOUND}
        for platform, attr in _SOCIAL_ATTR_MAP.items():
            if not getattr(lead, attr, None) and candidate.social_urls.get(platform):
                setattr(lead, attr, candidate.social_urls[platform])
                # Update presence status when a search-sourced URL is written in
                if platform == "instagram" and lead.instagram_presence_status in _downgradable:
                    lead.instagram_presence_status = SocialPresenceStatus.FOUND_VIA_SEARCH
                elif platform == "facebook" and lead.facebook_presence_status in _downgradable:
                    lead.facebook_presence_status = SocialPresenceStatus.FOUND_VIA_SEARCH

        if not lead.phone and candidate.phone:
            lead.phone = candidate.phone
        if not lead.email and candidate.email:
            lead.email = candidate.email
        if not lead.website_url and candidate.website_url:
            lead.website_url = candidate.website_url

        # Extend source_platforms without duplicates
        if candidate.source_platform not in lead.source_platforms:
            lead.source_platforms.append(candidate.source_platform)
