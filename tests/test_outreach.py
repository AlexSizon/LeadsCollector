"""
Unit tests for rule-based outreach generation.

The _generate_outreach_angle() and _generate_short_pitch() methods live inside
LeadPipeline. We test them by creating a LeadPipeline with mocked dependencies
and calling the methods directly.

Covers:
  - outreach_angle for NO_WEBSITE + strong reviews
  - outreach_angle for BROKEN_WEBSITE
  - outreach_angle for SOCIAL_ONLY
  - outreach_angle for HAS_WEBSITE with issues
  - short_pitch ≤ 3 sentences
  - short_pitch contains no pressure language ("must", "you need")
  - short_pitch references a concrete benefit
  - Niche-relevant language ("booking") for dentist/barbershop
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.models import BusinessLead
from src.enums import WebsiteStatus, InstagramStatus


# ---------------------------------------------------------------------------
# Helper: create a LeadPipeline without real API calls
# ---------------------------------------------------------------------------

def _make_pipeline():
    """Return a LeadPipeline instance with all external deps patched."""
    with patch("src.pipeline.GooglePlacesCollector") as mock_gpc, \
         patch("src.pipeline.WebsiteCollector"), \
         patch("src.pipeline.InstagramSignalCollector"):
        mock_gpc.return_value = MagicMock()
        from src.pipeline import LeadPipeline
        pipeline = LeadPipeline.__new__(LeadPipeline)
        pipeline.config = {}
        pipeline._city_weights = {}
        return pipeline


def _lead(
    company_name="My Salon",
    niche="beauty salon",
    city="Berlin",
    country="DE",
    website_status=WebsiteStatus.NO_WEBSITE,
    instagram_status=InstagramStatus.FOUND_ACTIVE,
    google_reviews_count=80,
    google_rating=4.6,
    issues_found=None,
) -> BusinessLead:
    lead = BusinessLead(
        company_name=company_name,
        niche=niche,
        city=city,
        country=country,
    )
    lead.website_status = website_status
    lead.instagram_status = instagram_status
    lead.google_reviews_count = google_reviews_count
    lead.google_rating = google_rating
    lead.issues_found = issues_found or []
    return lead


# ---------------------------------------------------------------------------
# _generate_outreach_angle
# ---------------------------------------------------------------------------

class TestOutreachAngle:
    def setup_method(self):
        self.pipeline = _make_pipeline()

    def test_no_website_strong_reviews(self):
        lead = _lead(
            website_status=WebsiteStatus.NO_WEBSITE,
            google_reviews_count=75,
        )
        angle = self.pipeline._generate_outreach_angle(lead)
        assert isinstance(angle, str)
        assert len(angle) > 0

    def test_no_website_mentioned_in_angle(self):
        lead = _lead(website_status=WebsiteStatus.NO_WEBSITE, google_reviews_count=60)
        angle = self.pipeline._generate_outreach_angle(lead)
        assert "website" in angle.lower() or "web" in angle.lower()

    def test_broken_website_in_angle(self):
        lead = _lead(website_status=WebsiteStatus.BROKEN_WEBSITE, google_reviews_count=30)
        angle = self.pipeline._generate_outreach_angle(lead)
        assert "broken" in angle.lower() or "unreachable" in angle.lower() or "website" in angle.lower()

    def test_social_only_in_angle(self):
        lead = _lead(website_status=WebsiteStatus.SOCIAL_ONLY)
        angle = self.pipeline._generate_outreach_angle(lead)
        assert len(angle) > 0

    def test_has_website_with_issues(self):
        lead = _lead(
            website_status=WebsiteStatus.HAS_WEBSITE,
            issues_found=["No click-to-call (tel:) link found", "Missing mobile viewport meta tag"],
        )
        angle = self.pipeline._generate_outreach_angle(lead)
        assert len(angle) > 0

    def test_angle_is_non_empty_even_on_sparse_lead(self):
        lead = _lead(
            website_status=WebsiteStatus.UNKNOWN,
            instagram_status=InstagramStatus.UNKNOWN,
            google_reviews_count=None,
            google_rating=None,
            issues_found=[],
        )
        angle = self.pipeline._generate_outreach_angle(lead)
        assert len(angle.strip()) > 0

    def test_angle_ends_with_period(self):
        lead = _lead(website_status=WebsiteStatus.NO_WEBSITE, google_reviews_count=100)
        angle = self.pipeline._generate_outreach_angle(lead)
        assert angle.endswith(".")


# ---------------------------------------------------------------------------
# _generate_short_pitch
# ---------------------------------------------------------------------------

PRESSURE_PHRASES = [
    "you must", "you need to", "you should", "you have to",
    "urgent", "immediately", "right now",
]


class TestShortPitch:
    def setup_method(self):
        self.pipeline = _make_pipeline()

    def test_pitch_is_non_empty(self):
        lead = _lead()
        pitch = self.pipeline._generate_short_pitch(lead)
        assert len(pitch.strip()) > 0

    def test_pitch_max_three_sentences(self):
        """The pitch should contain no more than 3 sentences."""
        lead = _lead(google_reviews_count=50)
        pitch = self.pipeline._generate_short_pitch(lead)
        # Split on . / ! / ? to count sentences
        import re
        sentences = [s.strip() for s in re.split(r"[.!?]+", pitch) if s.strip()]
        assert len(sentences) <= 3

    def test_no_pressure_language(self):
        """Pitch must not contain pushy / pressure phrases."""
        lead = _lead(website_status=WebsiteStatus.NO_WEBSITE)
        pitch = self.pipeline._generate_short_pitch(lead).lower()
        for phrase in PRESSURE_PHRASES:
            assert phrase not in pitch, f"Found pressure phrase: '{phrase}'"

    def test_no_website_pitch_mentions_benefit(self):
        """Pitch for no-website should mention customers, bookings, or contact."""
        lead = _lead(website_status=WebsiteStatus.NO_WEBSITE)
        pitch = self.pipeline._generate_short_pitch(lead).lower()
        assert any(w in pitch for w in ["customer", "booking", "contact", "website", "traffic"])

    def test_has_website_cta_issue_pitch(self):
        lead = _lead(
            website_status=WebsiteStatus.HAS_WEBSITE,
            issues_found=["No contact or booking form found on page"],
        )
        pitch = self.pipeline._generate_short_pitch(lead).lower()
        assert any(w in pitch for w in ["booking", "contact", "form", "appointment", "conversion"])

    def test_dentist_niche_mentions_booking(self):
        lead = _lead(niche="dentist", website_status=WebsiteStatus.NO_WEBSITE)
        pitch = self.pipeline._generate_short_pitch(lead).lower()
        assert "book" in pitch or "appointment" in pitch

    def test_social_only_pitch_mentions_ownership(self):
        lead = _lead(website_status=WebsiteStatus.SOCIAL_ONLY)
        pitch = self.pipeline._generate_short_pitch(lead).lower()
        assert any(w in pitch for w in ["owned", "website", "home", "booking"])
