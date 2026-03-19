#!/usr/bin/env python3
"""
Europe SMB Lead Discovery — OpenStreetMap Edition

Runs the full pipeline (discovery → enrichment → website audit →
Instagram signals → scoring → dedup → export) using OpenStreetMap /
Overpass API as the data source when no Google Places API key is present.

Usage
-----
    python -m run_europe_smb                          # use default config
    python -m run_europe_smb --config config/run_europe_smb.json
    GOOGLE_PLACES_API_KEY=key python -m run_europe_smb  # use Google Places instead
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

# ── Project root on sys.path ────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.collectors.overpass_collector import OverpassCollector, NICHE_NORMALIZATION
from src.collectors.website_collector import WebsiteCollector
from src.collectors.instagram_signal_collector import InstagramSignalCollector
from src.collectors.social_collector import SocialCollector
from src.collectors.instagram_discovery_collector import InstagramDiscoveryCollector
from src.collectors.facebook_discovery_collector import FacebookDiscoveryCollector
from src.collectors.tripadvisor_collector import TripAdvisorCollector
from src.enrichment.email_guesser import EmailGuesser
from src.auditors.technical_auditor import audit_technical
from src.auditors.seo_auditor import audit_seo
from src.auditors.ux_auditor import audit_ux
from src.scoring.business_strength import compute_business_strength
from src.scoring.website_problem import compute_website_problem_score
from src.scoring.commercial_opportunity import compute_commercial_opportunity
from src.scoring.instagram_signal import compute_instagram_signal
from src.scoring.final_score import compute_final_score, assign_tier
from src.scoring.contactability import compute_contactability_score
from src.enrichment.deduplicator import deduplicate_leads_with_report
from src.enrichment.cross_source_matcher import CrossSourceMatcher
from src.enrichment.contact_discovery import ContactDiscovery
from src.logging_utils import PipelineLogger, generate_run_id
from src.models import BusinessLead
from src.enums import WebsiteStatus, InstagramStatus, MatchConfidence
from src.output.exporter_json import export_json
from src.output.exporter_csv import export_csv
from src.outreach import (
    build_contact_provenance,
    classify_email_eligibility,
    derive_offer_type,
    generate_email_body_preview,
    generate_email_cta,
    generate_email_opening,
    generate_email_subject,
    load_policy_config,
)
from src.terminal_logging import NullTerminalLogger, TerminalRunLogger

log = logging.getLogger(__name__)

# ── Config ───────────────────────────────────────────────────────────────────
DEFAULT_CONFIG = str(ROOT / "config" / "run_europe_smb.json")
LOG_DIR = ROOT / "logs"
OUTREACH_POLICY_PATH = ROOT / "config" / "outreach_policy.json"


def load_config(path: str) -> Dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ── Pipeline ─────────────────────────────────────────────────────────────────

def run_pipeline(
    config: Dict,
    *,
    run_id: Optional[str] = None,
    terminal_logger: Optional[TerminalRunLogger] = None,
) -> List[BusinessLead]:
    cities           = config.get("cities", [])
    city_country_map = config.get("city_country_map", {})
    raw_niches       = config.get("niches", [])
    max_results      = config.get("max_results_per_query", 20)
    min_reviews      = config.get("min_reviews_threshold", 0)
    min_rating       = config.get("min_rating_threshold", 0.0)
    include_ig       = config.get("include_instagram_analysis", False)
    run_audit        = config.get("run_website_audit", True)
    request_delay    = config.get("request_delay", 1.0)
    enable_social_disc  = config.get("enable_social_discovery", False)
    enable_contact_disc = config.get("enable_contact_discovery", True)
    enable_ta_disc       = config.get("enable_tripadvisor_discovery", False)
    enable_email_guesser_flag = config.get("enable_email_guesser", False)
    social_delay        = config.get("social_request_delay", 3.0)
    run_id = run_id or generate_run_id()
    logger = PipelineLogger(run_id, LOG_DIR)
    terminal = terminal_logger or NullTerminalLogger()
    _run_start = time.monotonic()
    logger.log_run_start(config)

    # Deduplicate niche list (beauty salon + beauty studio → one canonical)
    canonical_niches: List[str] = []
    seen_niches: set = set()
    for n in raw_niches:
        canon = NICHE_NORMALIZATION.get(n.lower(), n.lower())
        if canon not in seen_niches:
            seen_niches.add(canon)
            canonical_niches.append(canon)

    collector = OverpassCollector(request_delay=request_delay)
    website_checker = WebsiteCollector(timeout=12)
    instagram_checker = InstagramSignalCollector()
    social_checker = SocialCollector()

    # Social discovery / contact discovery objects (only when flags enabled)
    ig_discovery: Optional[InstagramDiscoveryCollector] = (
        InstagramDiscoveryCollector(request_delay=social_delay) if enable_social_disc else None
    )
    fb_discovery: Optional[FacebookDiscoveryCollector] = (
        FacebookDiscoveryCollector(request_delay=social_delay) if enable_social_disc else None
    )
    matcher: Optional[CrossSourceMatcher] = CrossSourceMatcher() if enable_social_disc else None
    contact_disc: Optional[ContactDiscovery] = ContactDiscovery() if enable_contact_disc else None
    ta_discovery: Optional[TripAdvisorCollector] = (
        TripAdvisorCollector(request_delay=social_delay) if enable_ta_disc else None
    )
    email_guesser: Optional[EmailGuesser] = (
        EmailGuesser() if enable_email_guesser_flag else None
    )
    outreach_policy = load_policy_config(
        config.get("outreach_policy_path") or str(OUTREACH_POLICY_PATH)
    )

    # Load city attractiveness weights
    scoring_rules_path = ROOT / "config" / "scoring_rules.json"
    city_weights: Dict[str, float] = {}
    try:
        rules = json.loads(scoring_rules_path.read_text("utf-8"))
        city_weights = rules.get("city_attractiveness", {})
    except Exception:
        pass

    leads: List[BusinessLead] = []
    seen_osm_ids: set = set()

    total_cities = len(cities)
    total_niches = len(canonical_niches)
    total_queries = total_cities * total_niches
    query_count = 0

    try:
        terminal.batch(
            name="pipeline",
            detail=f"start cities={total_cities} niches={total_niches} query_slots={total_queries}",
        )

        for city in cities:
            country = city_country_map.get(city, "")
            city_weight = city_weights.get(city, city_weights.get("default", 1.0))
            city_lead_start_count = len(leads)

            for niche in canonical_niches:
                query_count += 1
                query = f"{niche} in {city}"
                terminal.query_start(index=query_count, total=total_queries, city=city, niche=niche)

                _q_start = time.monotonic()
                try:
                    places = collector.search(
                        query=query,
                        max_results=max_results,
                        city=city,
                        country=country,
                        niches=[niche],
                    )
                except Exception as exc:
                    logger.log_query(
                        city,
                        niche,
                        source="overpass",
                        result_count=0,
                        duration_s=time.monotonic() - _q_start,
                        error=str(exc),
                    )
                    terminal.query_result(
                        city=city,
                        niche=niche,
                        source="overpass",
                        result_count=0,
                        duration_s=time.monotonic() - _q_start,
                        status="upstream_error",
                        retry_count=0,
                        error=str(exc),
                    )
                    log.warning("Search failed for '%s': %s", query, exc)
                    continue

                query_meta = getattr(collector, "last_query_meta", {})
                if not isinstance(query_meta, dict):
                    query_meta = {}
                query_status = str(query_meta.get("status", "success" if places else "zero_results"))
                retry_count = int(query_meta.get("retry_count", 0))
                query_error = query_meta.get("error")
                logger.log_query(
                    city,
                    niche,
                    source="overpass",
                    result_count=len(places),
                    duration_s=time.monotonic() - _q_start,
                    error=query_error if query_status in {"upstream_error", "geocode_failed"} else None,
                )
                terminal.query_result(
                    city=city,
                    niche=niche,
                    source="overpass",
                    result_count=len(places),
                    duration_s=time.monotonic() - _q_start,
                    status=query_status,
                    retry_count=retry_count,
                    error=query_error if query_status in {"upstream_error", "geocode_failed"} else None,
                )

                for place in places:
                    osm_id = place.get("id", "")
                    if osm_id in seen_osm_ids:
                        continue
                    seen_osm_ids.add(osm_id)

                    # Basic filters
                    rating  = place.get("rating")
                    reviews = place.get("userRatingCount")
                    if rating  is not None and rating  < min_rating:
                        continue
                    if reviews is not None and reviews < min_reviews:
                        continue

                    company_name = place.get("displayName", {}).get("text", "")
                    if not company_name:
                        continue

                    # Get full details (from cache — no extra HTTP)
                    details   = collector.get_place_details(osm_id)
                    phone     = details.get("internationalPhoneNumber")
                    website   = details.get("websiteUri")
                    map_url   = details.get("googleMapsUri")
                    address   = details.get("formattedAddress", "")
                    assigned_niche = details.get("_niche", niche)

                    _lead_start = time.monotonic()
                    lead = BusinessLead(
                        company_name=company_name,
                        niche=assigned_niche,
                        country=country,
                        city=city,
                        place_id=osm_id,
                        address=address,
                        phone=phone,
                        google_rating=rating,
                        google_reviews_count=reviews,
                        website_url=website,
                        map_url=map_url,
                        lead_source="osm",
                        source_platforms=["osm"],
                    )
                    terminal.lead_stage(
                        company=company_name,
                        stage="start",
                        detail=f"city={city} niche={assigned_niche}",
                    )

                    # ── Stage 3: Website presence ────────────────────────────
                    website_response = None
                    if website:
                        try:
                            status, website_response = website_checker.check_website(website)
                        except Exception as exc:
                            log.debug("Website check error for %s: %s", website, exc)
                            status = WebsiteStatus.UNKNOWN
                    else:
                        status = WebsiteStatus.NO_WEBSITE
                    lead.website_status = status
                    terminal.lead_stage(
                        company=company_name,
                        stage="website",
                        detail=f"status={status.value}",
                    )

                    # ── Stage 3b: Website audit (HAS_WEBSITE only) ───────────
                    issues: List[str] = []
                    opps:   List[str] = []
                    if run_audit and status == WebsiteStatus.HAS_WEBSITE and website_response is not None:
                        try:
                            html = website_response.text
                            t_iss, t_opp = audit_technical(website, html, website_response)
                            s_iss, s_opp = audit_seo(website, html)
                            u_iss, u_opp = audit_ux(html)
                            issues = t_iss + s_iss + u_iss
                            opps   = t_opp + s_opp + u_opp
                        except Exception as exc:
                            log.debug("Audit error for %s: %s", website, exc)
                    lead.issues_found = issues
                    lead.improvement_opportunities = opps
                    if run_audit:
                        terminal.lead_stage(
                            company=company_name,
                            stage="audit",
                            detail=f"issues={len(issues)} opportunities={len(opps)}",
                        )

                    # ── Stage 4: Instagram signal ─────────────────────────────
                    insta_status = InstagramStatus.UNKNOWN
                    instagram_handle_found = False
                    if include_ig:
                        handle: Optional[str] = None
                        if website_response is not None and website_response.text:
                            try:
                                handle = instagram_checker.extract_handle_from_html(website_response.text)
                            except Exception:
                                pass

                        # Fallback: website_url itself might be an instagram profile
                        if not handle and website and "instagram.com" in website:
                            import re as _re
                            m = _re.search(r"instagram\.com/([A-Za-z0-9_.]{1,30})", website)
                            if m:
                                handle = m.group(1)

                        if handle:
                            instagram_handle_found = True
                            try:
                                insta_status = instagram_checker.analyze_handle(handle)
                            except Exception:
                                insta_status = InstagramStatus.UNKNOWN

                    lead.instagram_status = insta_status

                    # ── Stage 4b: Email + social media ───────────────────────
                    osm_tags = details.get("_osm_tags", {})
                    osm_social = SocialCollector.extract_from_osm_tags(osm_tags)
                    html_social: dict = {}
                    if website_response is not None and website_response.text:
                        try:
                            html_social = social_checker.extract_from_html(
                                website_response.text, website or ""
                            )
                        except Exception as exc:
                            log.debug("Social extraction error for %s: %s", website, exc)
                    social = SocialCollector.merge(html_social, osm_social)
                    lead.email        = social.get("email")
                    lead.facebook_url  = social.get("facebook")
                    lead.twitter_url   = social.get("twitter")
                    lead.tiktok_url    = social.get("tiktok")
                    lead.linkedin_url  = social.get("linkedin")
                    lead.youtube_url   = social.get("youtube")
                    lead.pinterest_url = social.get("pinterest")
                    lead.whatsapp_url  = social.get("whatsapp")
                    lead.telegram_url  = social.get("telegram")
                    if social.get("instagram"):
                        lead.instagram_url = social.get("instagram")

                    # ── Stage 4c: Contact discovery ──────────────────────────
                    contact_discovery_run = False
                    if enable_contact_disc and contact_disc is not None:
                        contact_discovery_run = True
                        try:
                            contact_result = contact_disc.extract(lead, website_response)
                            contact_disc.apply_to_lead(lead, contact_result)
                        except Exception as exc:
                            log.debug("Contact discovery error for %s: %s", company_name, exc)

                    # ── Stage 4d: Email guesser ──────────────────────────────
                    if (enable_email_guesser_flag and email_guesser is not None
                            and not lead.primary_email
                            and not (lead.all_emails and any(lead.all_emails))
                            and lead.website_url):
                        try:
                            guessed = email_guesser.guess(lead.website_url, lead.niche)
                            if guessed:
                                lead.guessed_email = guessed
                        except Exception as exc:
                            log.debug("Email guesser error for %s: %s", company_name, exc)
                    if contact_discovery_run:
                        terminal.lead_stage(
                            company=company_name,
                            stage="contact",
                            detail=f"emails={len(lead.all_emails)} guessed={'yes' if bool(lead.guessed_email) else 'no'}",
                        )

                    # ── Stage 5: Scoring ─────────────────────────────────────
                    lead.business_strength_score = compute_business_strength(rating, reviews)
                    lead.website_problem_score   = compute_website_problem_score(status, issues)
                    lead.commercial_opportunity_score = compute_commercial_opportunity(
                        status, assigned_niche,
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
                    )
                    lead.tier = assign_tier(
                        lead.lead_priority_score,
                        lead.business_strength_score,
                        lead.website_status.value,
                    )

                    # ── Outreach ─────────────────────────────────────────────
                    _apply_outreach_fields(lead, policy=outreach_policy)

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
                        "website_fetched": bool(website),
                        "audit_run": bool(run_audit and status == WebsiteStatus.HAS_WEBSITE and website_response is not None),
                        "json_ld_found": False,
                        "emails_found": emails_found,
                        "social_links_found": social_links_found,
                        "instagram_handle_found": instagram_handle_found,
                        "contact_discovery_run": contact_discovery_run,
                    }
                    logger.log_lead(lead, stages, time.monotonic() - _lead_start)
                    terminal.lead_complete(
                        company=company_name,
                        city=city,
                        niche=assigned_niche,
                        website_status=lead.website_status.value,
                        tier=lead.tier,
                        score=lead.lead_priority_score,
                    )
                    leads.append(lead)

            # ── Stage 2b: Social discovery (per city after niche queries) ─────
            if enable_social_disc and ig_discovery and fb_discovery and matcher:
                terminal.batch(name="social-discovery", detail=f"start city={city}")
                for niche in canonical_niches:
                    try:
                        ig_candidates = ig_discovery.search(niche, city, country, max_results)
                    except Exception as exc:
                        log.warning("Instagram discovery failed for %s/%s: %s", niche, city, exc)
                        ig_candidates = []
                    try:
                        fb_candidates = fb_discovery.search(niche, city, country, max_results)
                    except Exception as exc:
                        log.warning("Facebook discovery failed for %s/%s: %s", niche, city, exc)
                        fb_candidates = []
                    ta_candidates = []
                    if ta_discovery is not None:
                        try:
                            ta_candidates = ta_discovery.search(niche, city, country, max_results)
                        except Exception as exc:
                            log.warning("TripAdvisor discovery failed for %s/%s: %s", niche, city, exc)

                    for candidate in ig_candidates + fb_candidates + ta_candidates:
                        try:
                            result = matcher.match(candidate, leads)
                        except Exception as exc:
                            log.debug("Matcher error for candidate %s: %s", candidate.display_name, exc)
                            continue

                        if result.confidence == MatchConfidence.HIGH and result.matched_index is not None:
                            matcher.merge_into(candidate, leads[result.matched_index])
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
                                match_confidence=result.confidence.value,
                            )
                            # Populate social URL from candidate social_urls dict
                            for key, val in (candidate.social_urls or {}).items():
                                attr = f"{key}_url"
                                if hasattr(social_lead, attr) and not getattr(social_lead, attr):
                                    setattr(social_lead, attr, val)
                            # Score with defaults (no website / ratings data)
                            social_lead.contactability_score = compute_contactability_score(social_lead)
                            social_lead.lead_priority_score = compute_final_score(
                                social_lead.business_strength_score,
                                social_lead.website_problem_score,
                                social_lead.commercial_opportunity_score,
                                social_lead.instagram_signal_score,
                                social_lead.contactability_score,
                            )
                            social_lead.tier = assign_tier(
                                social_lead.lead_priority_score,
                                social_lead.business_strength_score,
                                social_lead.website_status.value,
                            )
                            _apply_outreach_fields(social_lead, policy=outreach_policy)
                            leads.append(social_lead)

            terminal.city_complete(
                city=city,
                completed_queries=query_count,
                total_queries=total_queries,
                leads_before_dedup=len(leads) - city_lead_start_count,
            )

        # ── Stage 6: Deduplication ───────────────────────────────────────────
        terminal.batch(name="dedup", detail=f"start count={len(leads)}")
        before = len(leads)
        leads, dedup_report = deduplicate_leads_with_report(leads)
        terminal.dedup_complete(
            before=before,
            after=len(leads),
            sample_reasons=dedup_report.sample_reasons,
        )

        return leads
    finally:
        try:
            logger.log_run_end(len(leads), time.monotonic() - _run_start)
        finally:
            logger.close()


# ── Outreach generation ──────────────────────────────────────────────────────
# (Rule-based, adapted from pipeline.py)

_BOOKING_NICHES = {"restaurant", "beauty salon", "bakery", "florist"}


def _apply_outreach_fields(
    lead: BusinessLead,
    *,
    policy: Dict,
    jld: Optional[Dict] = None,
    suppressed: bool = False,
) -> None:
    """Populate eligibility, provenance, and email draft fields."""
    lead.outreach_angle = _generate_outreach_angle(lead)
    lead.short_pitch = _generate_short_pitch(lead)
    lead.contact_provenance = build_contact_provenance(lead, jld=jld)

    eligibility, eligibility_reason, policy_decision, policy_reason, policy_version = (
        classify_email_eligibility(
            lead,
            policy=policy,
            suppressed=suppressed,
        )
    )
    lead.email_eligibility = eligibility.value
    lead.email_eligibility_reason = eligibility_reason
    lead.outreach_policy_decision = policy_decision.value
    lead.outreach_policy_reason = policy_reason
    lead.outreach_policy_version = policy_version

    offer_type = derive_offer_type(lead)
    lead.offer_type = offer_type.value
    lead.email_subject = generate_email_subject(lead)
    lead.email_opening = generate_email_opening(lead)
    lead.email_cta = generate_email_cta(lead)
    lead.email_body_preview = generate_email_body_preview(lead)

def _generate_outreach_angle(lead: BusinessLead) -> str:
    parts: List[str] = []

    if lead.google_reviews_count and lead.google_reviews_count >= 50:
        parts.append(f"Strong review profile ({lead.google_reviews_count} reviews)")
    elif lead.google_reviews_count and lead.google_reviews_count >= 20:
        parts.append(f"Established local reputation ({lead.google_reviews_count} reviews)")

    if lead.website_status == WebsiteStatus.NO_WEBSITE:
        parts.append("no owned website presence")
    elif lead.website_status == WebsiteStatus.BROKEN_WEBSITE:
        parts.append("website is currently broken or unreachable")
    elif lead.website_status == WebsiteStatus.SOCIAL_ONLY:
        parts.append("online presence limited to social/directory profiles")
    elif lead.website_status == WebsiteStatus.HAS_WEBSITE and lead.issues_found:
        cta_issues  = [i for i in lead.issues_found if any(w in i.lower() for w in ("cta", "booking", "call", "form"))]
        tech_issues = [i for i in lead.issues_found if any(w in i.lower() for w in ("mobile", "https", "ssl"))]
        if cta_issues:
            parts.append("weak conversion infrastructure")
        elif tech_issues:
            parts.append("technical issues affecting mobile usability")
        else:
            parts.append(f"{len(lead.issues_found)} website issues identified")

    if lead.instagram_status in (InstagramStatus.FOUND_ACTIVE, InstagramStatus.FOUND_ACTIVE_WITH_LINK):
        if lead.website_status != WebsiteStatus.HAS_WEBSITE:
            parts.append("active social presence without a web destination")

    if not parts:
        return "Moderate business with room for online optimisation."
    return " but ".join(parts[:2]) + "."


def _generate_short_pitch(lead: BusinessLead) -> str:
    sentences: List[str] = []

    if lead.google_reviews_count and lead.google_reviews_count >= 20:
        sentences.append(
            f"You already have visible local demand and {lead.google_reviews_count} reviews working in your favour."
        )

    if lead.website_status == WebsiteStatus.NO_WEBSITE:
        action = "booking" if lead.niche in _BOOKING_NICHES else "contact"
        sentences.append(
            f"A mobile-first website with a clear {action} flow "
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
        cta_related = any(any(w in i.lower() for w in ("cta", "booking", "form")) for i in lead.issues_found)
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


# ── Summary generation ───────────────────────────────────────────────────────

def generate_summary(
    leads: List[BusinessLead],
    config: Dict,
    elapsed_seconds: float,
    output_json: str,
    output_csv: str,
) -> str:
    total = len(leads)
    tier_counts = {1: 0, 2: 0, 3: 0, 4: 0}
    status_counts: Dict[str, int] = {}
    niche_counts:  Dict[str, int] = {}
    country_counts:Dict[str, int] = {}

    for lead in leads:
        tier_counts[lead.tier] = tier_counts.get(lead.tier, 0) + 1
        ws = lead.website_status.value
        status_counts[ws] = status_counts.get(ws, 0) + 1
        niche_counts[lead.niche] = niche_counts.get(lead.niche, 0) + 1
        country_counts[lead.country] = country_counts.get(lead.country, 0) + 1

    top10 = sorted(leads, key=lambda l: l.lead_priority_score, reverse=True)[:10]

    runtime = f"{int(elapsed_seconds // 60)}m {int(elapsed_seconds % 60)}s"
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    lines = [
        "# Europe SMB Lead Discovery — Run Summary",
        f"\n**Timestamp**: {ts}  ",
        f"**Runtime**: {runtime}  ",
        f"**Data source**: OpenStreetMap / Overpass API  ",
        f"**Countries**: Spain, Netherlands, Portugal  ",
        f"**Total leads collected**: {total}",
        "\n## Tier Distribution",
        f"| Tier | Count | Description |",
        f"|------|-------|-------------|",
        f"| 1 | {tier_counts[1]} | Strong business + no/broken website |",
        f"| 2 | {tier_counts[2]} | Good priority score (≥55) |",
        f"| 3 | {tier_counts[3]} | Moderate priority score (≥35) |",
        f"| 4 | {tier_counts[4]} | Low priority |",
        "\n## Website Status Breakdown",
    ]
    for ws, cnt in sorted(status_counts.items(), key=lambda x: -x[1]):
        lines.append(f"- **{ws}**: {cnt}")

    lines.append("\n## Leads by Country")
    for c, cnt in sorted(country_counts.items()):
        lines.append(f"- {c}: {cnt}")

    lines.append("\n## Leads by Niche")
    for n, cnt in sorted(niche_counts.items(), key=lambda x: -x[1]):
        lines.append(f"- {n}: {cnt}")

    lines.append("\n## Top 10 Leads by Priority Score")
    lines.append("| # | Company | Niche | City | Country | Score | Tier | Website Status |")
    lines.append("|---|---------|-------|------|---------|-------|------|----------------|")
    for i, lead in enumerate(top10, 1):
        lines.append(
            f"| {i} | {lead.company_name} | {lead.niche} | {lead.city} | "
            f"{lead.country} | {lead.lead_priority_score:.1f} | {lead.tier} | "
            f"{lead.website_status.value} |"
        )

    lines.append("\n## Output Files")
    lines.append(f"- JSON: `{output_json}`")
    lines.append(f"- CSV:  `{output_csv}`")

    lines.append("\n## Data Source Notes")
    lines.append("- **Data source**: OpenStreetMap (Overpass API + Nominatim geocoder)")
    lines.append("- **Google Places API**: not used — no API key configured")
    lines.append("- **google_rating / google_reviews_count**: `null` for all leads (OSM has no ratings)")
    lines.append("- **business_strength_score**: defaults to 20.0 (null-input neutral) for all leads")
    lines.append("- **Instagram analysis**: attempted for businesses with extractable handles")
    lines.append("- **Website audit**: full technical/SEO/UX audit ran for `HAS_WEBSITE` leads")

    return "\n".join(lines)


# ── Entry point ──────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Europe SMB pipeline (OSM edition)")
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    parser.add_argument(
        "--terminal-verbosity",
        choices=["normal", "verbose", "debug"],
        default=None,
        help="Terminal transcript verbosity (default: config value or normal)",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    terminal_verbosity = args.terminal_verbosity or config.get("terminal_verbosity", "normal")
    terminal_summary_every_queries = config.get("terminal_summary_every_queries", 5)
    output_cfg = config.get("output", {})
    output_json = str(ROOT / output_cfg.get("json", "output/leads.json"))
    output_csv  = str(ROOT / output_cfg.get("csv",  "output/leads.csv"))
    output_summary = str(ROOT / output_cfg.get("summary", "output/run_summary.md"))

    Path(output_json).parent.mkdir(parents=True, exist_ok=True)

    log.info("=== Europe SMB Lead Discovery (OSM) ===")
    run_id = generate_run_id()
    total_queries = len(config.get("cities", [])) * len(config.get("niches", []))

    with TerminalRunLogger(
        run_id,
        LOG_DIR,
        verbosity=terminal_verbosity,
        summary_every_queries=terminal_summary_every_queries,
    ) as terminal:
        terminal.run_start(
            entry_point="run_europe_smb.py",
            config=config,
            total_queries=total_queries,
            structured_log_path=LOG_DIR / f"pipeline_{run_id}.jsonl",
        )
        terminal.batch(name="config", detail=f"path={args.config}")
        terminal.batch(name="output", detail=f"json={output_json} csv={output_csv} summary={output_summary}")

        start = time.time()
        leads = run_pipeline(config, run_id=run_id, terminal_logger=terminal)
        elapsed = time.time() - start

        if not leads:
            log.warning("Pipeline produced 0 leads.")
        else:
            terminal.batch(name="pipeline", detail=f"done leads={len(leads)} duration={elapsed:.1f}s")

        leads_data = [lead.to_json() for lead in leads]
        website_status_counts = Counter(lead.website_status.value for lead in leads)
        terminal.final_summary(
            total_leads=len(leads),
            duration_s=elapsed,
            website_status_counts=website_status_counts,
        )

        terminal.batch(name="export", detail=f"start lead_count={len(leads_data)}")
        export_json(leads_data, output_json)
        terminal.export_complete(artifact="json", path=output_json)

        export_csv(leads_data, output_csv)
        terminal.export_complete(artifact="csv", path=output_csv)

        summary = generate_summary(leads, config, elapsed, output_json, output_csv)
        Path(output_summary).write_text(summary, encoding="utf-8")
        terminal.export_complete(artifact="summary", path=output_summary)

        # Quick tier breakdown to stdout
        tier_counts = {1: 0, 2: 0, 3: 0, 4: 0}
        for lead in leads:
            tier_counts[lead.tier] = tier_counts.get(lead.tier, 0) + 1

        print(f"\n{'='*52}")
        print(f"  RESULTS: {len(leads)} leads  ({elapsed:.0f}s)")
        print(f"  Tier 1: {tier_counts[1]}  |  Tier 2: {tier_counts[2]}  |  "
              f"Tier 3: {tier_counts[3]}  |  Tier 4: {tier_counts[4]}")
        print(f"  JSON → {output_json}")
        print(f"  CSV  → {output_csv}")
        print(f"  TERMINAL LOG → {terminal.transcript_path}")
        print(f"{'='*52}\n")


if __name__ == "__main__":
    main()
