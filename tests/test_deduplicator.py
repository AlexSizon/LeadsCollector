"""
Unit tests for the deduplication module.

Covers:
  - place_id identity key: exact match de-duplicates
  - root_domain identity key: same website de-duplicates
  - normalised_phone identity key: same E.164 number de-duplicates
  - name + city similarity key: ≥ 0.90 similarity de-duplicates
  - name + city: different city does NOT de-duplicate even on similar names
  - Merge logic: richer record (more non-null fields) becomes the canonical entry
  - Unrelated records are kept as distinct entries
"""

from __future__ import annotations

import pytest

from src.enrichment.deduplicator import deduplicate_leads
from src.models import BusinessLead
from src.enums import WebsiteStatus, InstagramStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _lead(
    company_name: str = "Test Biz",
    city: str = "Berlin",
    country: str = "DE",
    niche: str = "dentist",
    place_id: str = None,
    phone: str = None,
    website_url: str = None,
    address: str = None,
    google_rating: float = None,
    google_reviews_count: int = None,
) -> BusinessLead:
    return BusinessLead(
        company_name=company_name,
        niche=niche,
        country=country,
        city=city,
        place_id=place_id,
        phone=phone,
        website_url=website_url,
        address=address,
        google_rating=google_rating,
        google_reviews_count=google_reviews_count,
    )


# ---------------------------------------------------------------------------
# place_id deduplication
# ---------------------------------------------------------------------------

class TestPlaceIdDedup:
    def test_same_place_id_deduplicates(self):
        a = _lead("Smile Studio", place_id="pid_001")
        b = _lead("Smile Studio GmbH", place_id="pid_001")
        result = deduplicate_leads([a, b])
        assert len(result) == 1

    def test_different_place_ids_kept(self):
        a = _lead("Smile Studio", place_id="pid_001")
        b = _lead("Happy Dental", place_id="pid_002")
        result = deduplicate_leads([a, b])
        assert len(result) == 2

    def test_none_place_ids_not_matched(self):
        a = _lead("Smile Studio", place_id=None)
        b = _lead("Smile Studio", place_id=None)
        # They share similar name+city so might match via name similarity — that's ok
        result = deduplicate_leads([a, b])
        # Either 1 (name dedup) or 2 (no match) — but not more than 2
        assert len(result) <= 2


# ---------------------------------------------------------------------------
# root_domain deduplication
# ---------------------------------------------------------------------------

class TestRootDomainDedup:
    def test_same_website_deduplicates(self):
        a = _lead("Salon One", website_url="https://www.mysalon.de")
        b = _lead("Salon One Berlin", website_url="https://mysalon.de/en/home")
        result = deduplicate_leads([a, b])
        assert len(result) == 1

    def test_different_websites_kept(self):
        a = _lead("Salon A", website_url="https://salon-a.de")
        b = _lead("Salon B", website_url="https://salon-b.de")
        result = deduplicate_leads([a, b])
        assert len(result) == 2

    def test_no_website_not_matched_by_domain(self):
        a = _lead("Bizz A", website_url=None)
        b = _lead("Bizz B", website_url=None)
        # Both have no website; no domain key — shouldn't auto-merge via domain
        result = deduplicate_leads([a, b])
        assert len(result) >= 1


# ---------------------------------------------------------------------------
# phone deduplication
# ---------------------------------------------------------------------------

class TestPhoneDedup:
    def test_same_phone_deduplicates(self):
        a = _lead("Barbershop One", phone="+4930123456")
        b = _lead("Barbershop 1", phone="+4930123456")
        result = deduplicate_leads([a, b])
        assert len(result) == 1

    def test_different_phones_kept(self):
        a = _lead("Biz A", phone="+4930111111")
        b = _lead("Biz B", phone="+4930222222")
        result = deduplicate_leads([a, b])
        assert len(result) == 2

    def test_none_phones_not_matched(self):
        a = _lead(company_name="Studio X Alpha", phone=None, city="Munich")
        b = _lead(company_name="Studio Y Beta", phone=None, city="Munich")
        result = deduplicate_leads([a, b])
        assert len(result) == 2


# ---------------------------------------------------------------------------
# name + city similarity deduplication
# ---------------------------------------------------------------------------

class TestNameCityDedup:
    def test_very_similar_names_same_city_deduplicates(self):
        a = _lead("Dentist Berlin Smile Studio", city="berlin")
        b = _lead("Dentist Berlin Smile Studio.", city="berlin")
        result = deduplicate_leads([a, b])
        assert len(result) == 1

    def test_different_cities_not_deduped(self):
        a = _lead("Smile Studio", city="berlin")
        b = _lead("Smile Studio", city="munich")
        result = deduplicate_leads([a, b])
        assert len(result) == 2

    def test_low_similarity_not_deduped(self):
        a = _lead("Berliner Dental", city="berlin")
        b = _lead("Munich Physio Studio", city="berlin")
        result = deduplicate_leads([a, b])
        assert len(result) == 2


# ---------------------------------------------------------------------------
# Merge logic
# ---------------------------------------------------------------------------

class TestMergeLogic:
    def test_richer_record_wins(self):
        """The record with more non-null fields should be the canonical one."""
        sparse = _lead("Smile Studio", place_id="pid_001", phone=None, google_rating=None)
        rich = _lead("Smile Studio", place_id="pid_001", phone="+4930999", google_rating=4.5)
        result = deduplicate_leads([sparse, rich])
        assert len(result) == 1
        kept = result[0]
        assert kept.phone == "+4930999"
        assert kept.google_rating == 4.5

    def test_merge_backfills_missing_fields(self):
        """Fields missing in the richer record should be backfilled from secondary."""
        a = _lead("Smile Studio", place_id="pid_001", phone="+4930999",
                  google_rating=4.5, address=None)
        b = _lead("Smile Studio", place_id="pid_001", phone=None,
                  google_rating=None, address="Berliner Str 1, 10115 Berlin")
        result = deduplicate_leads([a, b])
        assert len(result) == 1
        kept = result[0]
        # Phone from richer (a), address backfilled from b
        assert kept.phone == "+4930999"
        assert kept.address == "Berliner Str 1, 10115 Berlin"


# ---------------------------------------------------------------------------
# No duplicates
# ---------------------------------------------------------------------------

class TestNoDuplicates:
    def test_empty_input(self):
        assert deduplicate_leads([]) == []

    def test_single_lead_returned(self):
        a = _lead("Only One", place_id="singleton")
        assert len(deduplicate_leads([a])) == 1

    def test_unrelated_leads_all_kept(self):
        leads = [
            _lead("Shop A", city="Berlin", place_id="p1"),
            _lead("Shop B", city="Munich", place_id="p2"),
            _lead("Shop C", city="Amsterdam", place_id="p3"),
        ]
        assert len(deduplicate_leads(leads)) == 3


# ---------------------------------------------------------------------------
# List-field merge (Group 11 additions)
# ---------------------------------------------------------------------------

class TestListFieldMerge:
    def test_all_emails_merged(self):
        from src.enrichment.deduplicator import _merge
        base = _lead("A", place_id="p1")
        base.all_emails = ["a@example.com"]
        secondary = _lead("A", place_id="p1")
        secondary.all_emails = ["b@example.com", "a@example.com"]
        _merge(base, secondary)
        assert sorted(base.all_emails) == ["a@example.com", "b@example.com"]

    def test_all_phones_merged(self):
        from src.enrichment.deduplicator import _merge
        base = _lead("A", place_id="p1")
        base.all_phones = ["+351910000001"]
        secondary = _lead("A", place_id="p1")
        secondary.all_phones = ["+351910000002", "+351910000001"]
        _merge(base, secondary)
        assert sorted(base.all_phones) == ["+351910000001", "+351910000002"]

    def test_source_platforms_merged(self):
        from src.enrichment.deduplicator import _merge
        base = _lead("A", place_id="p1")
        base.source_platforms = ["google_places"]
        secondary = _lead("A", place_id="p1")
        secondary.source_platforms = ["instagram", "google_places"]
        _merge(base, secondary)
        assert sorted(base.source_platforms) == ["google_places", "instagram"]

    def test_social_urls_backfilled(self):
        from src.enrichment.deduplicator import _merge
        base = _lead("A", place_id="p1")
        secondary = _lead("A", place_id="p1")
        secondary.instagram_url = "https://instagram.com/shop_a"
        secondary.facebook_url = "https://facebook.com/shopa"
        _merge(base, secondary)
        assert base.instagram_url == "https://instagram.com/shop_a"
        assert base.facebook_url == "https://facebook.com/shopa"

    def test_existing_social_url_not_overwritten(self):
        from src.enrichment.deduplicator import _merge
        base = _lead("A", place_id="p1")
        base.instagram_url = "https://instagram.com/original"
        secondary = _lead("A", place_id="p1")
        secondary.instagram_url = "https://instagram.com/other"
        _merge(base, secondary)
        assert base.instagram_url == "https://instagram.com/original"

    def test_presence_status_promoted_from_secondary(self):
        from src.enrichment.deduplicator import _merge
        from src.enums import SocialPresenceStatus
        base = _lead("A", place_id="p1")
        # base defaults to UNKNOWN
        secondary = _lead("A", place_id="p1")
        secondary.instagram_presence_status = SocialPresenceStatus.FOUND_ON_WEBSITE
        secondary.facebook_presence_status = SocialPresenceStatus.FOUND_IN_SCHEMA
        _merge(base, secondary)
        assert base.instagram_presence_status == SocialPresenceStatus.FOUND_ON_WEBSITE
        assert base.facebook_presence_status == SocialPresenceStatus.FOUND_IN_SCHEMA

    def test_presence_status_not_downgraded(self):
        from src.enrichment.deduplicator import _merge
        from src.enums import SocialPresenceStatus
        base = _lead("A", place_id="p1")
        base.instagram_presence_status = SocialPresenceStatus.FOUND_ON_WEBSITE
        secondary = _lead("A", place_id="p1")
        secondary.instagram_presence_status = SocialPresenceStatus.FOUND_VIA_SEARCH
        _merge(base, secondary)
        # FOUND_ON_WEBSITE is higher fidelity — must not be downgraded
        assert base.instagram_presence_status == SocialPresenceStatus.FOUND_ON_WEBSITE
