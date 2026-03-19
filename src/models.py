"""
Data models for representing businesses and lead scoring results.

This module defines both the typed pipeline-stage models (using Pydantic
for validation) and the final ``BusinessLead`` output container (dataclass).

Pipeline stage flow:
  InputConfig → RawBusinessRecord → EnrichedRecord → AuditResult → ScoredLead → BusinessLead

The ``BusinessLead`` dataclass is the primary output structure used by the
pipeline and matches the JSON result schema defined in the specification.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

try:
    from pydantic import BaseModel, Field as PydanticField
    _PYDANTIC_AVAILABLE = True
except ImportError:  # pragma: no cover
    _PYDANTIC_AVAILABLE = False

    class BaseModel:  # type: ignore[no-redef]
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

    def PydanticField(default=None, **kwargs):  # type: ignore[misc]
        return default

from .enums import (
    WebsiteStatus, InstagramStatus,
    LeadSourceType, MatchConfidence, ContactType, ContactCategory,
    SocialPresenceStatus,
)


# ---------------------------------------------------------------------------
# Pydantic models (pipeline-stage typed contracts)
# ---------------------------------------------------------------------------

class InputConfig(BaseModel):
    """Validated input configuration for a pipeline run."""

    countries: List[str] = PydanticField(default_factory=list)
    cities: List[str] = PydanticField(default_factory=list)
    niches: List[str] = PydanticField(default_factory=list)
    language_priority: List[str] = PydanticField(default_factory=lambda: ["en"])
    max_results_per_query: int = 20
    min_reviews_threshold: int = 0
    min_rating_threshold: float = 0.0
    include_instagram_analysis: bool = True
    run_website_audit: bool = True
    output_format: str = "json"
    enable_contact_discovery: bool = True
    enable_social_discovery: bool = False
    outreach_policy_path: Optional[str] = None
    outreach_store_path: str = "data/outreach.db"
    outreach_export_dir: str = "output/outreach_campaigns"
    outreach_execution_mode: str = "export-only"
    outreach_daily_send_limit: int = 50
    outreach_policy_version: str = "strict-email-first-v1"
    outreach_sender_profile: Dict[str, object] = PydanticField(default_factory=dict)


class RawBusinessRecord(BaseModel):
    """Raw output from the Google Places collection stage."""

    place_id: Optional[str] = None
    company_name: str = ""
    category: Optional[str] = None
    address: Optional[str] = None
    city: str = ""
    country: str = ""
    phone: Optional[str] = None
    website_url: Optional[str] = None
    rating: Optional[float] = None
    reviews_count: Optional[int] = None
    map_url: Optional[str] = None
    business_status: Optional[str] = None
    types: List[str] = PydanticField(default_factory=list)


class AuditResult(BaseModel):
    """Output from the website audit stage."""

    website_status: WebsiteStatus = WebsiteStatus.UNKNOWN
    issues_found: List[str] = PydanticField(default_factory=list)
    improvement_opportunities: List[str] = PydanticField(default_factory=list)


class EnrichedRecord(BaseModel):
    """A RawBusinessRecord after normalisation and enrichment."""

    place_id: Optional[str] = None
    company_name: str = ""
    normalised_name: Optional[str] = None
    category: Optional[str] = None
    address: Optional[str] = None
    city: str = ""
    country: str = ""
    phone: Optional[str] = None
    normalised_phone: Optional[str] = None
    website_url: Optional[str] = None
    root_domain: Optional[str] = None
    rating: Optional[float] = None
    reviews_count: Optional[int] = None
    map_url: Optional[str] = None
    is_smb: bool = True
    website_status: WebsiteStatus = WebsiteStatus.UNKNOWN
    instagram_handle: Optional[str] = None
    types: List[str] = PydanticField(default_factory=list)


class ScoredLead(BaseModel):
    """A fully scored lead with all sub-scores and tier classification."""

    business_strength_score: float = 0.0
    website_problem_score: float = 0.0
    commercial_opportunity_score: float = 0.0
    instagram_signal_score: float = 0.0
    lead_priority_score: float = 0.0
    tier: int = 4


# ---------------------------------------------------------------------------
# Social discovery intermediate models
# ---------------------------------------------------------------------------

@dataclass
class SocialCandidate:
    """A business candidate discovered from a social platform (Instagram/Facebook).

    This is an intermediate model that exists before cross-source matching.
    After matching it is either merged into an existing BusinessLead or
    promoted to a new one.
    """

    source_platform: str  # e.g. "instagram" or "facebook"
    handle_or_page_id: str = ""
    display_name: str = ""
    city: str = ""
    country: str = ""
    niche: str = ""
    website_url: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    social_urls: Dict[str, str] = field(default_factory=dict)
    raw_bio: Optional[str] = None


@dataclass
class MatchResult:
    """Result of matching a SocialCandidate against existing BusinessLeads."""

    confidence: MatchConfidence = MatchConfidence.UNMATCHED
    matched_index: Optional[int] = None


@dataclass
class ContactResult:
    """Structured contact data extracted by ContactDiscovery."""

    primary_email: Optional[str] = None
    all_emails: List[str] = field(default_factory=list)
    primary_phone: Optional[str] = None
    all_phones: List[str] = field(default_factory=list)
    whatsapp_links: List[str] = field(default_factory=list)
    messenger_links: List[str] = field(default_factory=list)
    booking_links: List[str] = field(default_factory=list)
    contact_form_urls: List[str] = field(default_factory=list)
    primary_contact_method: Optional[str] = None


# ---------------------------------------------------------------------------
# Primary output container (dataclass — mutable, pipeline-friendly)
# ---------------------------------------------------------------------------

@dataclass
class BusinessLead:
    """A fully enriched and scored business lead.

    This is the primary output structure. It stores all collected,
    enriched, audited and scored data for a single business and provides
    a ``to_json()`` helper that serialises into the canonical result schema.
    """

    company_name: str
    niche: str
    country: str
    city: str

    # Collected metadata
    place_id: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    google_rating: Optional[float] = None
    google_reviews_count: Optional[int] = None
    website_url: Optional[str] = None
    map_url: Optional[str] = None

    # Social media profiles
    facebook_url: Optional[str] = None
    twitter_url: Optional[str] = None
    tiktok_url: Optional[str] = None
    linkedin_url: Optional[str] = None
    youtube_url: Optional[str] = None
    pinterest_url: Optional[str] = None
    whatsapp_url: Optional[str] = None
    telegram_url: Optional[str] = None
    instagram_url: Optional[str] = None

    # Presence classification
    website_status: WebsiteStatus = WebsiteStatus.UNKNOWN
    instagram_status: InstagramStatus = InstagramStatus.UNKNOWN
    instagram_presence_status: SocialPresenceStatus = field(default_factory=lambda: SocialPresenceStatus.UNKNOWN)
    facebook_presence_status: SocialPresenceStatus = field(default_factory=lambda: SocialPresenceStatus.UNKNOWN)
    social_discovery_method: Optional[str] = None

    # Scores
    business_strength_score: float = 0.0
    website_problem_score: float = 0.0
    commercial_opportunity_score: float = 0.0
    instagram_signal_score: float = 0.0
    contactability_score: float = 0.0
    lead_priority_score: float = 0.0
    tier: int = 4

    # Audit findings
    issues_found: List[str] = field(default_factory=list)
    improvement_opportunities: List[str] = field(default_factory=list)

    # Outreach
    outreach_angle: str = ""
    short_pitch: str = ""

    # Source attribution
    lead_source: str = LeadSourceType.OSM.value
    source_platforms: List[str] = field(default_factory=lambda: [LeadSourceType.OSM.value])
    match_confidence: str = MatchConfidence.NA.value

    # Contact discovery
    primary_email: Optional[str] = None
    all_emails: List[str] = field(default_factory=list)
    primary_phone: Optional[str] = None
    all_phones: List[str] = field(default_factory=list)
    whatsapp_links: List[str] = field(default_factory=list)
    messenger_links: List[str] = field(default_factory=list)
    booking_links: List[str] = field(default_factory=list)
    contact_form_urls: List[str] = field(default_factory=list)
    primary_contact_method: Optional[str] = None

    # Email guessing (MX-verified, not scraped)
    guessed_email: Optional[str] = None

    # Outreach decision support
    contact_provenance: Dict[str, str] = field(default_factory=dict)
    email_eligibility: Optional[str] = None
    email_eligibility_reason: Optional[str] = None
    outreach_policy_decision: Optional[str] = None
    outreach_policy_reason: Optional[str] = None
    outreach_policy_version: Optional[str] = None
    offer_type: Optional[str] = None
    email_subject: Optional[str] = None
    email_opening: Optional[str] = None
    email_cta: Optional[str] = None
    email_body_preview: Optional[str] = None

    def to_json(self) -> Dict:
        """Convert the dataclass into a serialisable dict matching the JSON schema."""
        return {
            "company_name": self.company_name,
            "niche": self.niche,
            "country": self.country,
            "city": self.city,
            "address": self.address,
            "phone": self.phone,
            "email": self.email,
            "google_rating": self.google_rating,
            "google_reviews_count": self.google_reviews_count,
            "website_url": self.website_url,
            "website_status": self.website_status.value,
            "instagram_status": self.instagram_status.value,
            "instagram_presence_status": (self.instagram_presence_status.value if self.instagram_presence_status else SocialPresenceStatus.UNKNOWN.value),
            "facebook_presence_status": (self.facebook_presence_status.value if self.facebook_presence_status else SocialPresenceStatus.UNKNOWN.value),
            "social_discovery_method": self.social_discovery_method,
            "facebook_url": self.facebook_url,
            "twitter_url": self.twitter_url,
            "tiktok_url": self.tiktok_url,
            "linkedin_url": self.linkedin_url,
            "youtube_url": self.youtube_url,
            "pinterest_url": self.pinterest_url,
            "whatsapp_url": self.whatsapp_url,
            "telegram_url": self.telegram_url,
            "instagram_url": self.instagram_url,
            "business_strength_score": round(self.business_strength_score, 1),
            "website_problem_score": round(self.website_problem_score, 1),
            "commercial_opportunity_score": round(self.commercial_opportunity_score, 1),
            "instagram_signal_score": round(self.instagram_signal_score, 1),
            "lead_priority_score": round(self.lead_priority_score, 1),
            "contactability_score": round(self.contactability_score, 1),
            "tier": self.tier,
            "issues_found": self.issues_found,
            "improvement_opportunities": self.improvement_opportunities,
            "outreach_angle": self.outreach_angle,
            "short_pitch": self.short_pitch,
            # Source attribution
            "lead_source": self.lead_source,
            "source_platforms": self.source_platforms,
            "match_confidence": self.match_confidence,
            # Contact discovery
            "primary_email": self.primary_email,
            "all_emails": self.all_emails,
            "primary_phone": self.primary_phone,
            "all_phones": self.all_phones,
            "whatsapp_links": self.whatsapp_links,
            "messenger_links": self.messenger_links,
            "booking_links": self.booking_links,
            "contact_form_urls": self.contact_form_urls,
            "primary_contact_method": self.primary_contact_method,
            "guessed_email": self.guessed_email,
            "contact_provenance": self.contact_provenance,
            "email_eligibility": self.email_eligibility,
            "email_eligibility_reason": self.email_eligibility_reason,
            "outreach_policy_decision": self.outreach_policy_decision,
            "outreach_policy_reason": self.outreach_policy_reason,
            "outreach_policy_version": self.outreach_policy_version,
            "offer_type": self.offer_type,
            "email_subject": self.email_subject,
            "email_opening": self.email_opening,
            "email_cta": self.email_cta,
            "email_body_preview": self.email_body_preview,
        }
