"""
Functions for deduplicating business leads.

A lead is considered a duplicate if it matches any one of four identity keys:
  1. place_id         — definitive Google Places identifier
  2. root_domain      — same owned website
  3. normalised_phone — same E.164 phone number
  4. normalised_name + city — high-confidence name similarity (>= 0.90)

When duplicates are detected the richer record (most non-null fields) is kept
and any additional non-null fields from the secondary record are backfilled.
Deduplication runs as a post-collection batch pass.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Tuple

from ..models import BusinessLead
from .normalizer import normalize_phone, extract_root_domain, normalize_name

# Similarity threshold for normalised name + same city matching
_NAME_SIMILARITY_THRESHOLD = 0.90


@dataclass
class DeduplicationReport:
    removed_count: int = 0
    sample_reasons: List[str] = field(default_factory=list)

    def record(self, reason: str) -> None:
        self.removed_count += 1
        if reason and len(self.sample_reasons) < 5:
            self.sample_reasons.append(reason)


def _similarity(a: str, b: str) -> float:
    """Return SequenceMatcher ratio for two strings."""
    return SequenceMatcher(None, a, b).ratio()


def _count_non_null(lead: BusinessLead) -> int:
    """Count the number of non-None / non-empty fields on a lead."""
    count = 0
    for val in (
        lead.place_id, lead.address, lead.phone, lead.google_rating,
        lead.google_reviews_count, lead.website_url, lead.map_url,
        lead.outreach_angle, lead.short_pitch,
    ):
        if val is not None and val != "":
            count += 1
    count += len(lead.issues_found) + len(lead.improvement_opportunities)
    return count


def _merge(base: BusinessLead, secondary: BusinessLead) -> None:
    """Backfill missing fields from ``secondary`` into ``base`` (in-place)."""
    # Scalar fields — fill if base is empty
    if not base.place_id and secondary.place_id:
        base.place_id = secondary.place_id
    if not base.address and secondary.address:
        base.address = secondary.address
    if not base.phone and secondary.phone:
        base.phone = secondary.phone
    if base.google_rating is None and secondary.google_rating is not None:
        base.google_rating = secondary.google_rating
    if base.google_reviews_count is None and secondary.google_reviews_count is not None:
        base.google_reviews_count = secondary.google_reviews_count
    if not base.website_url and secondary.website_url:
        base.website_url = secondary.website_url
    if not base.map_url and secondary.map_url:
        base.map_url = secondary.map_url
    if not base.guessed_email and secondary.guessed_email:
        base.guessed_email = secondary.guessed_email
    if not base.social_discovery_method and secondary.social_discovery_method:
        base.social_discovery_method = secondary.social_discovery_method

    # Social URL fields — fill if base is empty
    for attr in (
        "facebook_url", "twitter_url", "instagram_url", "tiktok_url",
        "linkedin_url", "youtube_url", "pinterest_url", "whatsapp_url", "telegram_url",
    ):
        if not getattr(base, attr) and getattr(secondary, attr):
            setattr(base, attr, getattr(secondary, attr))

    # Presence status — promote secondary status if base is still UNKNOWN
    from ..enums import SocialPresenceStatus
    if (
        base.instagram_presence_status == SocialPresenceStatus.UNKNOWN
        and secondary.instagram_presence_status != SocialPresenceStatus.UNKNOWN
    ):
        base.instagram_presence_status = secondary.instagram_presence_status
    if (
        base.facebook_presence_status == SocialPresenceStatus.UNKNOWN
        and secondary.facebook_presence_status != SocialPresenceStatus.UNKNOWN
    ):
        base.facebook_presence_status = secondary.facebook_presence_status

    # List fields — union-merge without duplicates
    for attr in ("all_emails", "all_phones", "whatsapp_links", "messenger_links",
                 "booking_links", "contact_form_urls", "source_platforms"):
        base_list = getattr(base, attr, [])
        sec_list = getattr(secondary, attr, [])
        for item in sec_list:
            if item not in base_list:
                base_list.append(item)

    # Auditor output lists
    base.issues_found.extend(x for x in secondary.issues_found if x not in base.issues_found)
    base.improvement_opportunities.extend(
        x for x in secondary.improvement_opportunities if x not in base.improvement_opportunities
    )


def _format_duplicate_reason(
    *,
    key: str,
    value: str,
    city: str = "",
    similarity: float | None = None,
) -> str:
    if key == "place_id":
        return f"place_id={value}"
    if key == "root_domain":
        return f"root_domain={value}"
    if key == "phone":
        return f"phone={value}"
    if key == "name_city" and similarity is not None:
        return f"name+city city={city} similarity={similarity:.2f}"
    return key


def deduplicate_leads_with_report(leads: List[BusinessLead]) -> Tuple[List[BusinessLead], DeduplicationReport]:
    """Remove duplicate leads and return a deduplicated list.

    For each lead, checks four identity keys in order. When a match is
    found the richer of the two records is kept as the canonical entry.
    """
    place_id_index: Dict[str, BusinessLead] = {}
    phone_index: Dict[str, BusinessLead] = {}
    domain_index: Dict[str, BusinessLead] = {}
    # (normalised_name, city) -> BusinessLead for similarity lookup
    name_city_index: List[Tuple[str, str, BusinessLead]] = []

    unique: List[BusinessLead] = []
    report = DeduplicationReport()

    for lead in leads:
        place_key: Optional[str] = lead.place_id or None
        phone_key: Optional[str] = normalize_phone(lead.phone) if lead.phone else None
        domain_key: Optional[str] = extract_root_domain(lead.website_url) if lead.website_url else None
        norm_name = normalize_name(lead.company_name)
        city_lower = lead.city.lower().strip()

        existing: Optional[BusinessLead] = None
        duplicate_reason: str | None = None

        # --- Key 1: place_id ---
        if place_key and place_key in place_id_index:
            existing = place_id_index[place_key]
            duplicate_reason = _format_duplicate_reason(key="place_id", value=place_key)

        # --- Key 2: root_domain ---
        if existing is None and domain_key and domain_key in domain_index:
            existing = domain_index[domain_key]
            duplicate_reason = _format_duplicate_reason(key="root_domain", value=domain_key)

        # --- Key 3: normalised phone ---
        if existing is None and phone_key and phone_key in phone_index:
            existing = phone_index[phone_key]
            duplicate_reason = _format_duplicate_reason(key="phone", value=phone_key)

        # --- Key 4: normalised name + city similarity ---
        if existing is None:
            for stored_name, stored_city, stored_lead in name_city_index:
                similarity = _similarity(norm_name, stored_name)
                if stored_city == city_lower and similarity >= _NAME_SIMILARITY_THRESHOLD:
                    existing = stored_lead
                    duplicate_reason = _format_duplicate_reason(
                        key="name_city",
                        value=stored_name,
                        city=lead.city,
                        similarity=similarity,
                    )
                    break

        if existing:
            report.record(duplicate_reason or "unknown")
            # Keep the richer record as base
            if _count_non_null(lead) > _count_non_null(existing):
                _merge(lead, existing)
                # Replace existing in unique list with the richer record
                unique = [lead if ld is existing else ld for ld in unique]
                # Update indexes to point to the new base
                if place_key:
                    place_id_index[place_key] = lead
                if phone_key:
                    phone_index[phone_key] = lead
                if domain_key:
                    domain_index[domain_key] = lead
                name_city_index = [
                    (n, c, lead) if ld is existing else (n, c, ld)
                    for n, c, ld in name_city_index
                ]
            else:
                _merge(existing, lead)
        else:
            unique.append(lead)
            if place_key:
                place_id_index[place_key] = lead
            if phone_key:
                phone_index[phone_key] = lead
            if domain_key:
                domain_index[domain_key] = lead
            name_city_index.append((norm_name, city_lower, lead))

    return unique, report


def deduplicate_leads(leads: List[BusinessLead]) -> List[BusinessLead]:
    unique, _ = deduplicate_leads_with_report(leads)
    return unique
