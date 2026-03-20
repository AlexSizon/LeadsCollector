"""
Main orchestration pipeline for discovering and scoring SMB leads.

Six stages:
1. Lead discovery via Google Places text search
2. Business enrichment and normalisation
3. Website presence detection + audit
4. Instagram signal analysis
5. Lead scoring and prioritisation
6. Deduplication
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import List, Optional

from .logging_utils import PipelineLogger, generate_run_id
from .search_vocabulary import build_search_variants, get_search_languages
from .terminal_logging import NullTerminalLogger, TerminalRunLogger

_LOG_DIR = Path(__file__).resolve().parent.parent / "logs"

from .collectors.google_places_collector import GooglePlacesCollector
from .collectors.overpass_collector import OverpassCollector
from .collectors.website_collector import WebsiteCollector
from .collectors.instagram_signal_collector import InstagramSignalCollector
from .collectors.instagram_discovery_collector import InstagramDiscoveryCollector
from .collectors.facebook_discovery_collector import FacebookDiscoveryCollector
from .collectors.social_collector import SocialCollector
from .enrichment.normalizer import normalize_name, normalize_phone, extract_root_domain
from .enrichment.deduplicator import deduplicate_leads_with_report
from .enrichment.contact_discovery import ContactDiscovery
from .enrichment.cross_source_matcher import CrossSourceMatcher
from .enrichment.email_guesser import EmailGuesser
from .enrichment import json_ld_extractor
from .models import BusinessLead
from .enums import WebsiteStatus, InstagramStatus, MatchConfidence, SocialPresenceStatus, LeadSourceType
from .auditors.technical_auditor import audit_technical
from .auditors.seo_auditor import audit_seo
from .auditors.ux_auditor import audit_ux
from .scoring.business_strength import compute_business_strength
from .scoring.website_problem import compute_website_problem_score
from .scoring.commercial_opportunity import compute_commercial_opportunity
from .scoring.instagram_signal import compute_instagram_signal
from .scoring.contactability import compute_contactability_score
from .scoring.final_score import compute_final_score, assign_tier

_log = logging.getLogger(__name__)

# Known link-hub domains — when a social link resolves to one of these,
# we fetch the hub page and re-run social extraction.
_LINK_HUB_DOMAINS = frozenset({
    "linktr.ee",
    "beacons.ai",
    "bio.site",
    "solo.to",
    "taplink.cc",
})

# Load city attractiveness weights from scoring_rules.json
_SCORING_RULES_PATH = Path(__file__).resolve().parent.parent / "config" / "scoring_rules.json"
_NICHES_PATH = Path(__file__).resolve().parent.parent / "config" / "niches.json"

def _load_city_weights() -> dict:
    try:
        with open(_SCORING_RULES_PATH, encoding="utf-8") as f:
            rules = json.load(f)
        return rules.get("city_attractiveness", {})
    except Exception:
        return {}


def _load_scoring_weights() -> dict:
    """Load final_score_weights from scoring_rules.json."""
    try:
        with open(_SCORING_RULES_PATH, encoding="utf-8") as f:
            rules = json.load(f)
        return rules.get("final_score_weights", {})
    except Exception:
        return {}


def _load_niche_demand_weights() -> dict:
    """Load local_demand_weight per niche from niches.json."""
    try:
        with open(_NICHES_PATH, encoding="utf-8") as f:
            niches_data = json.load(f)
        result = {}
        for niche_key, niche_info in niches_data.get("niches", {}).items():
            result[niche_key] = niche_info.get("local_demand_weight", 1.0)
        return result
    except Exception:
        return {}


class LeadPipeline:
    """Pipeline orchestrator for SMB lead discovery and analysis."""

    def __init__(
        self,
        config: dict,
        api_key: str,
        *,
        run_id: Optional[str] = None,
        terminal_logger: Optional[TerminalRunLogger] = None,
    ):
        self.config = config
        request_delay = config.get("request_delay", 0.3)
        self.places = GooglePlacesCollector(api_key=api_key, request_delay=request_delay)
        self._overpass = OverpassCollector()
        self.website = WebsiteCollector()
        self.instagram = InstagramSignalCollector()
        self._social_collector = SocialCollector()
        self._city_weights = _load_city_weights()
        self._final_score_weights = _load_scoring_weights()
        self._niche_demand_weights = _load_niche_demand_weights()

        enable_contact = config.get("enable_contact_discovery", True)
        self._contact_discovery: Optional[ContactDiscovery] = ContactDiscovery() if enable_contact else None

        enable_guesser = config.get("enable_email_guesser", True)
        self._email_guesser: Optional[EmailGuesser] = EmailGuesser() if enable_guesser else None

        self._enable_linktree_resolution = config.get("enable_linktree_resolution", True)

        self._run_id = run_id or generate_run_id()
        self._logger = PipelineLogger(self._run_id, _LOG_DIR)
        self._terminal_logger = terminal_logger or NullTerminalLogger()

        enable_social = config.get("enable_social_discovery", False)
        if enable_social:
            social_delay = config.get("social_request_delay", 2.0)
            self._ig_discovery: Optional[InstagramDiscoveryCollector] = InstagramDiscoveryCollector(request_delay=social_delay)
            self._fb_discovery: Optional[FacebookDiscoveryCollector] = FacebookDiscoveryCollector(request_delay=social_delay)
            self._matcher: Optional[CrossSourceMatcher] = CrossSourceMatcher()
        else:
            self._ig_discovery = None
            self._fb_discovery = None
            self._matcher = None

    def run(self) -> List[BusinessLead]:
        leads: List[BusinessLead] = []
        niches: List[str] = self.config.get("niches", [])
        cities: List[str] = self.config.get("cities", [])
        countries: List[str] = self.config.get("countries", [])
        max_results: int = self.config.get("max_results_per_query", 10)
        min_reviews: int = self.config.get("min_reviews_threshold", 0)
        min_rating: float = self.config.get("min_rating_threshold", 0.0)
        response_languages: List[str] = self.config.get("language_priority", ["en"])
        search_languages: List[str] = get_search_languages(self.config)
        include_instagram: bool = self.config.get("include_instagram_analysis", False)
        run_audit: bool = self.config.get("run_website_audit", False)
        total_queries = len(countries) * len(cities) * sum(
            len(build_search_variants(niche, search_languages))
            for niche in niches
        )
        query_index = 0

        _run_start = time.monotonic()
        self._logger.log_run_start(self.config)

        seen_place_ids: set = set()

        try:
            for country in countries:
                for city in cities:
                    city_weight: float = self._city_weights.get(city, self._city_weights.get("default", 1.0))
                    city_lead_start_count = len(leads)
                    for niche in niches:
                        for search_language, search_label in build_search_variants(niche, search_languages):
                            query_index += 1
                            query = f"{search_label} in {city}"
                            response_lang = response_languages[0] if response_languages else "en"
                            _source_is_osm = False
                            _google_failed = False
                            _q_start = time.monotonic()
                            self._terminal_logger.query_start(
                                index=query_index,
                                total=total_queries,
                                city=city,
                                niche=niche,
                                search_language=search_language,
                            )
                            try:
                                places = self.places.search(
                                    query=query,
                                    max_results=max_results,
                                    language=response_lang,
                                )
                            except Exception as _places_exc:
                                _google_failed = True
                                _log.warning(
                                    "GooglePlaces failed for '%s', falling back to Overpass: %s",
                                    query, _places_exc,
                                )
                                try:
                                    places = self._overpass.search(
                                        query=query,
                                        max_results=max_results,
                                        language=response_lang,
                                        city=city,
                                        country=country,
                                        niches=[niche],
                                    )
                                    _source_is_osm = True
                                except Exception:
                                    self._logger.log_query(
                                        city,
                                        niche,
                                        source="overpass",
                                        result_count=0,
                                        duration_s=time.monotonic() - _q_start,
                                        search_language=search_language,
                                        fallback=True,
                                        error="both sources failed",
                                    )
                                    self._terminal_logger.query_result(
                                        city=city,
                                        niche=niche,
                                        search_language=search_language,
                                        source="overpass",
                                        result_count=0,
                                        duration_s=time.monotonic() - _q_start,
                                        status="upstream_error",
                                        retry_count=0,
                                        fallback=True,
                                        error="both_sources_failed",
                                    )
                                    continue

                            query_source = "overpass" if _source_is_osm else "google_places"
                            query_error = None
                            retry_count = 0
                            if _source_is_osm:
                                overpass_meta = getattr(self._overpass, "last_query_meta", {})
                                if not isinstance(overpass_meta, dict):
                                    overpass_meta = {}
                                retry_count = int(overpass_meta.get("retry_count", 0))
                                base_status = str(overpass_meta.get("status", "success" if places else "zero_results"))
                                query_error = overpass_meta.get("error")
                                if _google_failed:
                                    if base_status == "success":
                                        query_status = "fallback_success"
                                    elif base_status == "success_after_retry":
                                        query_status = "fallback_success_after_retry"
                                    elif base_status == "zero_results":
                                        query_status = "fallback_zero_results"
                                    else:
                                        query_status = base_status
                                else:
                                    query_status = base_status
                            else:
                                query_status = "zero_results" if len(places) == 0 else "success"

                            self._logger.log_query(
                                city,
                                niche,
                                source=query_source,
                                result_count=len(places),
                                duration_s=time.monotonic() - _q_start,
                                search_language=search_language,
                                fallback=_source_is_osm,
                                error=query_error if query_status in {"upstream_error", "geocode_failed"} else None,
                            )
                            self._terminal_logger.query_result(
                                city=city,
                                niche=niche,
                                search_language=search_language,
                                source=query_source,
                                result_count=len(places),
                                duration_s=time.monotonic() - _q_start,
                                status=query_status,
                                retry_count=retry_count,
                                fallback=_source_is_osm,
                                error=query_error if query_status in {"upstream_error", "geocode_failed"} else None,
                            )

                            for place in places:
                                place_id = place.get("id")

                                # -- Skip duplicates across queries --
                                if place_id and place_id in seen_place_ids:
                                    continue
                                if place_id:
                                    seen_place_ids.add(place_id)

                                # -- Rating / reviews pre-filter --
                                rating = place.get("rating")
                                reviews = place.get("userRatingCount")
                                if rating is not None and rating < min_rating:
                                    continue
                                if reviews is not None and reviews < min_reviews:
                                    continue

                                company_name = place.get("displayName", {}).get("text", "")
                                formatted_address = place.get("formattedAddress", "")

                                # -- Fetch Place Details --
                                details: dict = {}
                                if place_id:
                                    try:
                                        details = self.places.get_place_details(place_id, language=response_lang)
                                    except Exception:
                                        pass

                                phone: Optional[str] = details.get("internationalPhoneNumber")
                                website_url: Optional[str] = details.get("websiteUri")
                                map_url: Optional[str] = details.get("googleMapsUri")
                                rating = details.get("rating", rating)
                                reviews = details.get("userRatingCount", reviews)

                                # -- Build initial lead --
                                _lead_start = time.monotonic()
                                lead = BusinessLead(
                                    company_name=company_name,
                                    niche=niche,
                                    country=country,
                                    city=city,
                                    place_id=place_id,
                                    address=formatted_address,
                                    phone=phone,
                                    google_rating=rating,
                                    google_reviews_count=reviews,
                                    website_url=website_url,
                                    map_url=map_url,
                                )
                                if _source_is_osm:
                                    lead.lead_source = LeadSourceType.OSM.value
                                self._terminal_logger.lead_stage(
                                    company=company_name or "<unknown>",
                                    stage="start",
                                    detail=f"city={city} niche={niche}",
                                )

                                # ------------------------------------------------------------------
                                # Stage 3: Website presence detection
                                # ------------------------------------------------------------------
                                website_response = None
                                if website_url:
                                    status, website_response = self.website.check_website(website_url)
                                else:
                                    status = WebsiteStatus.NO_WEBSITE
                                lead.website_status = status
                                self._terminal_logger.lead_stage(
                                    company=company_name or "<unknown>",
                                    stage="website",
                                    detail=f"status={status.value}",
                                )

                                # ------------------------------------------------------------------
                                # Stage 3b: Website audit (only if HAS_WEBSITE)
                                # ------------------------------------------------------------------
                                issues: List[str] = []
                                opportunities: List[str] = []
                                if run_audit and status == WebsiteStatus.HAS_WEBSITE and website_response is not None:
                                    html = website_response.text
                                    tech_issues, tech_opps = audit_technical(
                                        website_url, html, website_response
                                    )
                                    seo_issues, seo_opps = audit_seo(website_url, html)
                                    ux_issues, ux_opps = audit_ux(html)
                                    issues = tech_issues + seo_issues + ux_issues
                                    opportunities = tech_opps + seo_opps + ux_opps

                                lead.issues_found = issues
                                lead.improvement_opportunities = opportunities
                                if run_audit:
                                    self._terminal_logger.lead_stage(
                                        company=company_name or "<unknown>",
                                        stage="audit",
                                        detail=f"issues={len(issues)} opportunities={len(opportunities)}",
                                    )

                                # ------------------------------------------------------------------
                                # Stage 3b2: Social link extraction from website HTML
                                # ------------------------------------------------------------------
                                _SOCIAL_PLATFORM_FIELDS = {
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
                                jld = {}
                                if status == WebsiteStatus.HAS_WEBSITE and website_response is not None:
                                    html_text = website_response.text

                                    # Step 1: SocialCollector — inline links in HTML
                                    social_data = self._social_collector.extract_from_html(html_text, website_url or "")
                                    for platform, attr in _SOCIAL_PLATFORM_FIELDS.items():
                                        val = social_data.get(platform)
                                        if val and not getattr(lead, attr):
                                            setattr(lead, attr, val)
                                    if lead.instagram_url and lead.instagram_presence_status == SocialPresenceStatus.UNKNOWN:
                                        lead.instagram_presence_status = SocialPresenceStatus.FOUND_ON_WEBSITE
                                        lead.social_discovery_method = "website_html"
                                    if lead.facebook_url and lead.facebook_presence_status == SocialPresenceStatus.UNKNOWN:
                                        lead.facebook_presence_status = SocialPresenceStatus.FOUND_ON_WEBSITE
                                        if not lead.social_discovery_method:
                                            lead.social_discovery_method = "website_html"

                                    # Step 2: JSON-LD — schema.org structured data
                                    jld = json_ld_extractor.extract_from_html(html_text) or {}
                                    if jld:
                                        if jld.get("phone") and not lead.phone:
                                            lead.phone = normalize_phone(jld["phone"]) or jld["phone"]
                                        if jld.get("email"):
                                            jld_email = jld["email"].lower()
                                            if jld_email not in [e.lower() for e in lead.all_emails]:
                                                lead.all_emails.append(jld_email)
                                        for soc_url in jld.get("social_urls", []):
                                            if "instagram.com" in soc_url and not lead.instagram_url:
                                                lead.instagram_url = soc_url
                                                lead.instagram_presence_status = SocialPresenceStatus.FOUND_IN_SCHEMA
                                                lead.social_discovery_method = "json_ld"
                                            elif "facebook.com" in soc_url and not lead.facebook_url:
                                                lead.facebook_url = soc_url
                                                lead.facebook_presence_status = SocialPresenceStatus.FOUND_IN_SCHEMA
                                                if not lead.social_discovery_method:
                                                    lead.social_discovery_method = "json_ld"
                                            elif "twitter.com" in soc_url or "x.com" in soc_url:
                                                if not lead.twitter_url:
                                                    lead.twitter_url = soc_url
                                            elif "linkedin.com" in soc_url and not lead.linkedin_url:
                                                lead.linkedin_url = soc_url
                                            elif "tiktok.com" in soc_url and not lead.tiktok_url:
                                                lead.tiktok_url = soc_url
                                            elif "youtube.com" in soc_url and not lead.youtube_url:
                                                lead.youtube_url = soc_url
                                            elif "pinterest.com" in soc_url and not lead.pinterest_url:
                                                lead.pinterest_url = soc_url

                                    # Step 3: Linktree hub resolution
                                    if self._enable_linktree_resolution:
                                        hub_url: Optional[str] = None
                                        for _, attr in _SOCIAL_PLATFORM_FIELDS.items():
                                            url_val = getattr(lead, attr)
                                            if url_val:
                                                domain_part = extract_root_domain(url_val)
                                                if domain_part in _LINK_HUB_DOMAINS:
                                                    hub_url = url_val
                                                    break
                                        if hub_url:
                                            try:
                                                import requests as _requests
                                                hub_resp = _requests.get(
                                                    hub_url,
                                                    timeout=5,
                                                    headers={"User-Agent": "Mozilla/5.0"},
                                                )
                                                if hub_resp.ok:
                                                    hub_data = self._social_collector.extract_from_html(
                                                        hub_resp.text, hub_url
                                                    )
                                                    for platform, attr in _SOCIAL_PLATFORM_FIELDS.items():
                                                        val = hub_data.get(platform)
                                                        if val and not getattr(lead, attr):
                                                            setattr(lead, attr, val)
                                                    if lead.instagram_url and lead.instagram_presence_status == SocialPresenceStatus.UNKNOWN:
                                                        lead.instagram_presence_status = SocialPresenceStatus.FOUND_VIA_HUB
                                                        lead.social_discovery_method = "linktree_hub"
                                                    elif lead.instagram_url and lead.social_discovery_method is None:
                                                        lead.social_discovery_method = "linktree_hub"
                                                    if lead.facebook_url and lead.facebook_presence_status == SocialPresenceStatus.UNKNOWN:
                                                        lead.facebook_presence_status = SocialPresenceStatus.FOUND_VIA_HUB
                                            except Exception as _hub_exc:
                                                _log.debug("Hub resolution failed for %s: %s", hub_url, _hub_exc)

                                # ------------------------------------------------------------------
                                # Stage 3c: Contact discovery (only if HAS_WEBSITE)
                                # ------------------------------------------------------------------
                                contact_discovery_run = False
                                if self._contact_discovery is not None and status == WebsiteStatus.HAS_WEBSITE and website_response is not None:
                                    contact_discovery_run = True
                                    try:
                                        contact_result = self._contact_discovery.extract(lead, website_response)
                                        self._contact_discovery.apply_to_lead(lead, contact_result)
                                    except Exception as exc:
                                        _log.debug("ContactDiscovery error for %s: %s", company_name, exc)
                                if contact_discovery_run:
                                    self._terminal_logger.lead_stage(
                                        company=company_name or "<unknown>",
                                        stage="contact",
                                        detail=f"emails={len(lead.all_emails)} guessed={'yes' if bool(lead.guessed_email) else 'no'}",
                                    )

                                # EmailGuesser fallback — only when no emails found yet
                                if (
                                    self._email_guesser is not None
                                    and not lead.all_emails
                                    and not lead.guessed_email
                                    and status == WebsiteStatus.HAS_WEBSITE
                                    and website_url
                                ):
                                    try:
                                        guessed = self._email_guesser.guess(website_url, lead.niche)
                                        if guessed:
                                            lead.guessed_email = guessed
                                    except Exception as exc:
                                        _log.debug("EmailGuesser failed for %s: %s", company_name, exc)

                                # ------------------------------------------------------------------
                                # Stage 4: Instagram signal analysis
                                # ------------------------------------------------------------------
                                insta_status = InstagramStatus.UNKNOWN
                                instagram_handle_found = False
                                if include_instagram:
                                    handle: Optional[str] = None

                                    # Use instagram_url already discovered by SocialCollector / JSON-LD
                                    if lead.instagram_url:
                                        from re import search as _re_search
                                        m = _re_search(r"instagram\.com/([A-Za-z0-9_.]{1,30})", lead.instagram_url)
                                        if m:
                                            handle = m.group(1)

                                    # Fallback: check if website_url itself is an Instagram URL
                                    if not handle and website_url and "instagram.com" in website_url:
                                        from re import search as _re_search
                                        m = _re_search(r"instagram\.com/([A-Za-z0-9_.]{1,30})", website_url)
                                        if m:
                                            handle = m.group(1)

                                    if handle:
                                        instagram_handle_found = True
                                        insta_status = self.instagram.analyze_handle(handle)
                                    else:
                                        insta_status = InstagramStatus.UNKNOWN

                                lead.instagram_status = insta_status

                                # ------------------------------------------------------------------
                                # Stage 5: Lead scoring
                                # ------------------------------------------------------------------
                                niche_weight = self._niche_demand_weights.get(niche, 1.0)
                                lead.business_strength_score = compute_business_strength(rating, reviews, niche_weight=niche_weight)
                                lead.website_problem_score = compute_website_problem_score(status, issues)
                                lead.commercial_opportunity_score = compute_commercial_opportunity(
                                    status, niche,
                                    city_demand_weight=city_weight,
                                    instagram_status=insta_status,
                                )
                                lead.instagram_signal_score = compute_instagram_signal(insta_status)
                                lead.contactability_score = compute_contactability_score(lead)
                                lead.lead_priority_score = compute_final_score(
                                    lead.business_strength_score,
                                    lead.website_problem_score,
                                    lead.commercial_opportunity_score,
                                    lead.instagram_signal_score,
                                    lead.contactability_score,
                                    weights=self._final_score_weights or None,
                                )
                                lead.tier = assign_tier(
                                    lead.lead_priority_score,
                                    lead.business_strength_score,
                                    lead.website_status.value,
                                )

                                # ------------------------------------------------------------------
                                # Outreach angle & short pitch
                                # ------------------------------------------------------------------
                                lead.outreach_angle = self._generate_outreach_angle(lead)
                                lead.short_pitch = self._generate_short_pitch(lead)

                                emails_found = len({
                                    email.lower()
                                    for email in [lead.email, lead.primary_email, lead.guessed_email, *lead.all_emails]
                                    if email
                                })
                                social_links_found = sum(
                                    1 for value in (
                                        lead.facebook_url,
                                        lead.twitter_url,
                                        lead.instagram_url,
                                        lead.tiktok_url,
                                        lead.linkedin_url,
                                        lead.youtube_url,
                                        lead.pinterest_url,
                                        lead.whatsapp_url,
                                        lead.telegram_url,
                                    )
                                    if value
                                )
                                stages = {
                                    "website_fetched": bool(website_url),
                                    "audit_run": bool(run_audit and status == WebsiteStatus.HAS_WEBSITE and website_response is not None),
                                    "json_ld_found": bool(jld),
                                    "emails_found": emails_found,
                                    "social_links_found": social_links_found,
                                    "instagram_handle_found": instagram_handle_found,
                                    "contact_discovery_run": contact_discovery_run,
                                }
                                self._logger.log_lead(lead, stages, time.monotonic() - _lead_start)
                                self._terminal_logger.lead_complete(
                                    company=company_name or "<unknown>",
                                    city=city,
                                    niche=niche,
                                    website_status=lead.website_status.value,
                                    tier=lead.tier,
                                    score=lead.lead_priority_score,
                                )
                                leads.append(lead)
                    self._terminal_logger.city_complete(
                        city=city,
                        completed_queries=query_index,
                        total_queries=total_queries,
                        leads_before_dedup=len(leads) - city_lead_start_count,
                    )

            # ------------------------------------------------------------------
            # Stage 5b: Social discovery (Instagram + Facebook) per niche × city
            # ------------------------------------------------------------------
            _stub_contact_queue: List[BusinessLead] = []  # task 9.1: stubs with website_url needing contact enrichment
            if self._ig_discovery is not None and self._fb_discovery is not None and self._matcher is not None:
                for country in countries:
                    for city in cities:
                        for niche in niches:
                            candidates = []
                            for search_language, search_label in build_search_variants(niche, search_languages):
                                try:
                                    candidates.extend(
                                        self._ig_discovery.search(
                                            niche,
                                            city,
                                            country,
                                            max_results,
                                            search_term=search_label,
                                        )
                                    )
                                except Exception:
                                    pass
                                try:
                                    candidates.extend(
                                        self._fb_discovery.search(
                                            niche,
                                            city,
                                            country,
                                            max_results,
                                            search_term=search_label,
                                        )
                                    )
                                except Exception:
                                    pass

                            for candidate in candidates:
                                try:
                                    match_result = self._matcher.match(candidate, leads)
                                except Exception:
                                    continue

                                if match_result.confidence == MatchConfidence.HIGH and match_result.matched_index is not None:
                                    self._matcher.merge_into(candidate, leads[match_result.matched_index])
                                else:
                                    # Promote social-only candidate to a lead stub
                                    social_lead = BusinessLead(
                                        company_name=candidate.display_name or "",
                                        niche=candidate.niche or niche,
                                        city=candidate.city or city,
                                        country=candidate.country or country,
                                        phone=candidate.phone,
                                        email=candidate.email,
                                        website_url=candidate.website_url,
                                        lead_source=candidate.source_platform,
                                        source_platforms=[candidate.source_platform],
                                        match_confidence=match_result.confidence.value,
                                    )
                                    # Populate social URLs from candidate (including instagram_url)
                                    for key, val in (candidate.social_urls or {}).items():
                                        attr = f"{key}_url"
                                        if hasattr(social_lead, attr) and not getattr(social_lead, attr):
                                            setattr(social_lead, attr, val)
                                    # Mark social URL discovery method for search-sourced stubs
                                    if social_lead.instagram_url:
                                        social_lead.instagram_presence_status = SocialPresenceStatus.FOUND_VIA_SEARCH
                                        social_lead.social_discovery_method = "search_fallback"
                                    if social_lead.facebook_url:
                                        social_lead.facebook_presence_status = SocialPresenceStatus.FOUND_VIA_SEARCH
                                        if not social_lead.social_discovery_method:
                                            social_lead.social_discovery_method = "search_fallback"
                                    # Score social stub
                                    social_lead.contactability_score = compute_contactability_score(social_lead)
                                    social_lead.lead_priority_score = compute_final_score(
                                        social_lead.business_strength_score,
                                        social_lead.website_problem_score,
                                        social_lead.commercial_opportunity_score,
                                        social_lead.instagram_signal_score,
                                        social_lead.contactability_score,
                                        weights=self._final_score_weights or None,
                                    )
                                    social_lead.tier = assign_tier(
                                        social_lead.lead_priority_score,
                                        social_lead.business_strength_score,
                                        social_lead.website_status.value,
                                    )
                                    social_lead.outreach_angle = self._generate_outreach_angle(social_lead)
                                    social_lead.short_pitch = self._generate_short_pitch(social_lead)
                                    leads.append(social_lead)
                                    # task 9.1: queue stubs with a website for deferred contact discovery
                                    if social_lead.website_url:
                                        _stub_contact_queue.append(social_lead)

            # task 9.2: Run ContactDiscovery on queued social-stub leads after Stage 5b
            # task 9.3: Run EmailGuesser on stubs with website URL and no emails
            for _stub in _stub_contact_queue:
                try:
                    _stub_status, _stub_resp = self.website.check_website(_stub.website_url)
                except Exception:
                    continue
                if _stub_status == WebsiteStatus.HAS_WEBSITE and _stub_resp is not None:
                    if self._contact_discovery is not None:
                        try:
                            _stub_result = self._contact_discovery.extract(_stub, _stub_resp)
                            self._contact_discovery.apply_to_lead(_stub, _stub_result)
                        except Exception as _exc:
                            _log.debug("ContactDiscovery error for stub %s: %s", _stub.company_name, _exc)
                    if self._email_guesser is not None and not _stub.all_emails and not _stub.guessed_email:
                        try:
                            _guessed = self._email_guesser.guess(_stub.website_url, _stub.niche)
                            if _guessed:
                                _stub.guessed_email = _guessed
                        except Exception as _exc:
                            _log.debug("EmailGuesser failed for stub %s: %s", _stub.company_name, _exc)

            # Finalise presence statuses — leads still UNKNOWN with no URL → NOT_FOUND
            for _lead in leads:
                if (
                    _lead.instagram_presence_status == SocialPresenceStatus.UNKNOWN
                    and not _lead.instagram_url
                ):
                    _lead.instagram_presence_status = SocialPresenceStatus.NOT_FOUND
                if (
                    _lead.facebook_presence_status == SocialPresenceStatus.UNKNOWN
                    and not _lead.facebook_url
                ):
                    _lead.facebook_presence_status = SocialPresenceStatus.NOT_FOUND

            self._terminal_logger.batch(name="dedup", detail=f"start count={len(leads)}")
            before_dedup = len(leads)
            leads, dedup_report = deduplicate_leads_with_report(leads)
            self._terminal_logger.dedup_complete(
                before=before_dedup,
                after=len(leads),
                sample_reasons=dedup_report.sample_reasons,
            )
            return leads
        finally:
            try:
                self._logger.log_run_end(len(leads), time.monotonic() - _run_start)
            finally:
                self._logger.close()

    # ------------------------------------------------------------------
    # Outreach helpers
    # ------------------------------------------------------------------

    def _generate_outreach_angle(self, lead: BusinessLead) -> str:
        """Formulate the outreach angle based on observed evidence signals only."""
        parts: List[str] = []

        # Business strength signal
        if lead.google_reviews_count and lead.google_reviews_count >= 50:
            parts.append(f"Strong review profile ({lead.google_reviews_count} reviews)")
        elif lead.google_reviews_count and lead.google_reviews_count >= 20:
            parts.append(f"Established local reputation ({lead.google_reviews_count} reviews)")

        # Website gap signal
        if lead.website_status == WebsiteStatus.NO_WEBSITE:
            parts.append("no owned website presence")
        elif lead.website_status == WebsiteStatus.BROKEN_WEBSITE:
            parts.append("website is currently broken or unreachable")
        elif lead.website_status == WebsiteStatus.SOCIAL_ONLY:
            parts.append("online presence limited to social/directory profiles")
        elif lead.website_status == WebsiteStatus.HAS_WEBSITE and lead.issues_found:
            # Surface the most commercially relevant issue
            cta_issues = [i for i in lead.issues_found if "cta" in i.lower() or "booking" in i.lower() or "call" in i.lower()]
            tech_issues = [i for i in lead.issues_found if "mobile" in i.lower() or "https" in i.lower() or "ssl" in i.lower()]
            if cta_issues:
                parts.append("weak conversion infrastructure")
            elif tech_issues:
                parts.append("technical issues affecting mobile usability")
            else:
                parts.append(f"{len(lead.issues_found)} website issues identified")

        # Instagram amplifier
        if lead.instagram_status in (InstagramStatus.FOUND_ACTIVE, InstagramStatus.FOUND_ACTIVE_WITH_LINK):
            if lead.website_status != WebsiteStatus.HAS_WEBSITE:
                parts.append("active social presence without a web destination")

        if not parts:
            return "Moderate business with room for online optimisation."

        return " but ".join(parts[:2]) + ("." if not parts[0].endswith(".") else "")

    def _generate_short_pitch(self, lead: BusinessLead) -> str:
        """Compose a concise, evidence-based pitch (1–3 sentences, no pressure language)."""
        sentences: List[str] = []

        # Opening: establish social proof if present
        if lead.google_reviews_count and lead.google_reviews_count >= 20:
            sentences.append(
                f"You already have visible local demand and {lead.google_reviews_count} reviews working in your favour."
            )

        # Core benefit based on primary gap
        if lead.website_status == WebsiteStatus.NO_WEBSITE:
            sentences.append(
                f"A mobile-first website with a clear {'booking' if lead.niche in ('dentist','barbershop','beauty salon') else 'contact'} flow "
                "could convert more of that traffic into actual customers."
            )
        elif lead.website_status == WebsiteStatus.BROKEN_WEBSITE:
            sentences.append(
                "Getting the website back online with a clear contact path could help capture customers who are ready to book."
            )
        elif lead.website_status == WebsiteStatus.SOCIAL_ONLY:
            sentences.append(
                "An owned website would give you a permanent home for bookings and enquiries beyond social platforms."
            )
        elif lead.issues_found:
            cta_related = any("cta" in i.lower() or "booking" in i.lower() or "form" in i.lower() for i in lead.issues_found)
            if cta_related:
                sentences.append(
                    "Improving the booking and contact flow on your current site could meaningfully increase appointment requests."
                )
            else:
                sentences.append(
                    "Addressing the technical and SEO basics on your current site could improve visibility and conversion."
                )

        if not sentences:
            return "There is potential to strengthen your online presence and make it easier for customers to reach you."

        return " ".join(sentences[:3])
