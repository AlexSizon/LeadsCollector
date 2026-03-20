"""
End-to-end smoke test for the LeadPipeline.

All external calls (Google Places, website fetch, Instagram) are mocked.
The test exercises the full pipeline.run() path and validates:
  - The return type is a list of BusinessLead instances
  - Each lead carries a non-zero lead_priority_score
  - to_json() produces a dict with the required schema keys
  - Duplicate place_ids are deduplicated by the pipeline
  - A lead with no website gets WebsiteStatus.NO_WEBSITE
"""

from __future__ import annotations

import json
from typing import List
from unittest.mock import MagicMock, patch

import pytest

from src.models import BusinessLead
from src.enums import WebsiteStatus, InstagramStatus
from src.search_vocabulary import build_search_variants, get_search_languages, resolve_search_label


# ---------------------------------------------------------------------------
# Required JSON output keys (per spec)
# ---------------------------------------------------------------------------

REQUIRED_JSON_KEYS = {
    "company_name",
    "niche",
    "country",
    "city",
    "address",
    "phone",
    "google_rating",
    "google_reviews_count",
    "website_url",
    "website_status",
    "instagram_status",
    "business_strength_score",
    "website_problem_score",
    "commercial_opportunity_score",
    "instagram_signal_score",
    "lead_priority_score",
    "tier",
    "issues_found",
    "improvement_opportunities",
    "outreach_angle",
    "short_pitch",
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MINIMAL_CONFIG = {
    "countries": ["DE"],
    "cities": ["Berlin"],
    "niches": ["dentist"],
    "language_priority": ["en"],
    "max_results_per_query": 5,
    "min_reviews_threshold": 0,
    "min_rating_threshold": 0.0,
    "include_instagram_analysis": False,
    "run_website_audit": False,
    "request_delay": 0,
}


def _places_search_result():
    return [
        {
            "id": "place_smoke_001",
            "displayName": {"text": "Smile Dental Berlin"},
            "formattedAddress": "Unter den Linden 1, 10117 Berlin",
            "businessStatus": "OPERATIONAL",
            "rating": 4.6,
            "userRatingCount": 88,
        }
    ]


def _place_details_result():
    return {
        "id": "place_smoke_001",
        "displayName": {"text": "Smile Dental Berlin"},
        "formattedAddress": "Unter den Linden 1, 10117 Berlin",
        "internationalPhoneNumber": "+49 30 12345678",
        "rating": 4.6,
        "userRatingCount": 88,
        "websiteUri": None,  # no website → NO_WEBSITE path
        "googleMapsUri": "https://maps.google.com/?cid=12345",
        "businessStatus": "OPERATIONAL",
        "types": ["dentist"],
    }


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------

class TestPipelineSmoke:
    """Full pipeline run with all external calls mocked."""

    def _run_pipeline(self, config=None, include_instagram=False):
        cfg = config or {**MINIMAL_CONFIG, "include_instagram_analysis": include_instagram}

        with patch("src.pipeline.GooglePlacesCollector") as MockGPC, \
             patch("src.pipeline.WebsiteCollector") as MockWC, \
             patch("src.pipeline.InstagramSignalCollector") as MockIG:

            # Configure Google Places mock
            mock_places = MagicMock()
            mock_places.search.return_value = _places_search_result()
            mock_places.get_place_details.return_value = _place_details_result()
            MockGPC.return_value = mock_places

            # Website collector mock — site has no website so skip HTTP
            mock_website = MagicMock()
            mock_website.check_website.return_value = (WebsiteStatus.NO_WEBSITE, None)
            MockWC.return_value = mock_website

            # Instagram collector mock
            mock_ig = MagicMock()
            mock_ig.extract_handle_from_html.return_value = None
            mock_ig.analyze_handle.return_value = InstagramStatus.UNKNOWN
            MockIG.return_value = mock_ig

            from src.pipeline import LeadPipeline
            pipeline = LeadPipeline(config=cfg, api_key="test-key")
            return pipeline.run()

    def test_run_returns_list(self):
        results = self._run_pipeline()
        assert isinstance(results, list)

    def test_run_returns_business_leads(self):
        results = self._run_pipeline()
        assert len(results) >= 1
        for lead in results:
            assert isinstance(lead, BusinessLead)

    def test_lead_has_nonzero_priority_score(self):
        results = self._run_pipeline()
        for lead in results:
            assert lead.lead_priority_score > 0

    def test_no_website_lead_status_correct(self):
        results = self._run_pipeline()
        for lead in results:
            assert lead.website_status == WebsiteStatus.NO_WEBSITE

    def test_lead_tier_assigned(self):
        results = self._run_pipeline()
        for lead in results:
            assert lead.tier in (1, 2, 3, 4)

    def test_to_json_has_all_required_keys(self):
        results = self._run_pipeline()
        assert len(results) >= 1
        data = results[0].to_json()
        missing = REQUIRED_JSON_KEYS - set(data.keys())
        assert not missing, f"Missing JSON keys: {missing}"

    def test_to_json_website_status_is_string(self):
        results = self._run_pipeline()
        data = results[0].to_json()
        assert isinstance(data["website_status"], str)

    def test_to_json_issues_is_list(self):
        results = self._run_pipeline()
        data = results[0].to_json()
        assert isinstance(data["issues_found"], list)
        assert isinstance(data["improvement_opportunities"], list)

    def test_outreach_angle_non_empty(self):
        results = self._run_pipeline()
        for lead in results:
            assert isinstance(lead.outreach_angle, str)
            assert len(lead.outreach_angle.strip()) > 0

    def test_short_pitch_non_empty(self):
        results = self._run_pipeline()
        for lead in results:
            assert isinstance(lead.short_pitch, str)
            assert len(lead.short_pitch.strip()) > 0

    def test_duplicate_place_id_deduplicated(self):
        """If the same place_id appears twice (e.g. from two queries), it should dedup."""
        with patch("src.pipeline.GooglePlacesCollector") as MockGPC, \
             patch("src.pipeline.WebsiteCollector") as MockWC, \
             patch("src.pipeline.InstagramSignalCollector"):

            mock_places = MagicMock()
            # Return same place for two different niches
            mock_places.search.return_value = _places_search_result()
            mock_places.get_place_details.return_value = _place_details_result()
            MockGPC.return_value = mock_places

            mock_website = MagicMock()
            mock_website.check_website.return_value = (WebsiteStatus.NO_WEBSITE, None)
            MockWC.return_value = mock_website

            cfg = {**MINIMAL_CONFIG, "niches": ["dentist", "dentist"]}
            from src.pipeline import LeadPipeline
            pipeline = LeadPipeline(config=cfg, api_key="test-key")
            results = pipeline.run()

            # Two identical place_ids from two queries should yield exactly one lead
            place_ids = [r.place_id for r in results]
            assert len(place_ids) == len(set(place_ids)), "Duplicate place_ids found in output"

    def test_empty_config_returns_empty_list(self):
        """Pipeline with no configured niches/cities should return empty list."""
        with patch("src.pipeline.GooglePlacesCollector"), \
             patch("src.pipeline.WebsiteCollector"), \
             patch("src.pipeline.InstagramSignalCollector"):
            cfg = {**MINIMAL_CONFIG, "niches": [], "cities": []}
            from src.pipeline import LeadPipeline
            pipeline = LeadPipeline(config=cfg, api_key="test-key")
            results = pipeline.run()
            assert results == []

    def test_places_api_error_is_swallowed(self):
        """If search() raises an exception, the pipeline should continue (not crash)."""
        with patch("src.pipeline.GooglePlacesCollector") as MockGPC, \
             patch("src.pipeline.WebsiteCollector"), \
             patch("src.pipeline.InstagramSignalCollector"):

            mock_places = MagicMock()
            mock_places.search.side_effect = ConnectionError("API down")
            MockGPC.return_value = mock_places

            from src.pipeline import LeadPipeline
            pipeline = LeadPipeline(config=MINIMAL_CONFIG, api_key="test-key")
            results = pipeline.run()
            # Should not raise; returns empty list (no leads collected)
            assert isinstance(results, list)

    def test_pipeline_creates_jsonl_log_with_run_start_and_run_end(self, tmp_path, monkeypatch):
        with patch("src.pipeline.GooglePlacesCollector") as MockGPC, \
             patch("src.pipeline.WebsiteCollector") as MockWC, \
             patch("src.pipeline.InstagramSignalCollector") as MockIG:

            mock_places = MagicMock()
            mock_places.search.return_value = _places_search_result()
            mock_places.get_place_details.return_value = _place_details_result()
            MockGPC.return_value = mock_places

            mock_website = MagicMock()
            mock_website.check_website.return_value = (WebsiteStatus.NO_WEBSITE, None)
            MockWC.return_value = mock_website

            mock_ig = MagicMock()
            mock_ig.extract_handle_from_html.return_value = None
            mock_ig.analyze_handle.return_value = InstagramStatus.UNKNOWN
            MockIG.return_value = mock_ig

            import src.pipeline as pipeline_module

            monkeypatch.setattr(pipeline_module, "_LOG_DIR", tmp_path / "logs")
            pipeline = pipeline_module.LeadPipeline(config=MINIMAL_CONFIG, api_key="test-key")
            pipeline.run()

        log_files = sorted((tmp_path / "logs").glob("pipeline_*.jsonl"))
        assert len(log_files) == 1

        events = [
            json.loads(line)
            for line in log_files[0].read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        event_types = {event["event"] for event in events}
        assert "run_start" in event_types
        assert "run_end" in event_types

    def test_multilingual_search_expands_queries_and_keeps_canonical_niche(self):
        with patch("src.pipeline.GooglePlacesCollector") as MockGPC, \
             patch("src.pipeline.WebsiteCollector") as MockWC, \
             patch("src.pipeline.InstagramSignalCollector"):

            mock_places = MagicMock()
            mock_places.search.return_value = _places_search_result()
            mock_places.get_place_details.return_value = {
                **_place_details_result(),
                "websiteUri": None,
            }
            MockGPC.return_value = mock_places

            mock_website = MagicMock()
            mock_website.check_website.return_value = (WebsiteStatus.NO_WEBSITE, None)
            MockWC.return_value = mock_website

            cfg = {
                **MINIMAL_CONFIG,
                "countries": ["Ukraine"],
                "cities": ["Kyiv"],
                "niches": ["beauty salon"],
                "search_languages": ["en", "uk", "ru"],
            }
            from src.pipeline import LeadPipeline
            pipeline = LeadPipeline(config=cfg, api_key="test-key")
            results = pipeline.run()

            observed_queries = [call.kwargs["query"] for call in mock_places.search.call_args_list]
            assert observed_queries == [
                "beauty salon in Kyiv",
                "салон краси in Kyiv",
                "салон красоты in Kyiv",
            ]
            assert mock_places.get_place_details.call_count == 1
            assert len(results) == 1
            assert results[0].niche == "beauty salon"

    def test_missing_translation_falls_back_to_canonical_label(self):
        assert resolve_search_label("dentist", "it") == "dentist"
        assert build_search_variants("dentist", ["it"]) == [("it", "dentist")]

    def test_search_languages_omitted_uses_canonical_query(self):
        with patch("src.pipeline.GooglePlacesCollector") as MockGPC, \
             patch("src.pipeline.WebsiteCollector") as MockWC, \
             patch("src.pipeline.InstagramSignalCollector"):

            mock_places = MagicMock()
            mock_places.search.return_value = _places_search_result()
            mock_places.get_place_details.return_value = _place_details_result()
            MockGPC.return_value = mock_places

            mock_website = MagicMock()
            mock_website.check_website.return_value = (WebsiteStatus.NO_WEBSITE, None)
            MockWC.return_value = mock_website

            from src.pipeline import LeadPipeline
            pipeline = LeadPipeline(config=MINIMAL_CONFIG, api_key="test-key")
            pipeline.run()

            observed_queries = [call.kwargs["query"] for call in mock_places.search.call_args_list]
            assert observed_queries == ["dentist in Berlin"]

    def test_get_search_languages_normalizes_and_deduplicates(self):
        assert get_search_languages({
            "search_languages": ["EN", "uk", "en", " ", "RU"],
        }) == ["en", "uk", "ru"]


# ---------------------------------------------------------------------------
# Presence status integration (task 13.5)
# ---------------------------------------------------------------------------

_WEBSITE_HTML_WITH_SOCIALS = """
<html><body>
<a href="https://www.instagram.com/smiledental_berlin">Instagram</a>
<a href="https://www.facebook.com/smiledental">Facebook</a>
</body></html>
"""

_PLACE_WITH_WEBSITE = {
    "id": "place_presence_001",
    "displayName": {"text": "Smile Dental Berlin"},
    "formattedAddress": "Friedrichstr 10, 10117 Berlin",
    "internationalPhoneNumber": "+49 30 99999999",
    "rating": 4.5,
    "userRatingCount": 55,
    "websiteUri": "https://smiledental-berlin.de",
    "googleMapsUri": "https://maps.google.com/?cid=99999",
    "businessStatus": "OPERATIONAL",
    "types": ["dentist"],
}


class TestPresenceStatusIntegration:
    """Verify that instagram_presence_status and facebook_presence_status are
    correctly populated after a full pipeline run for a lead with a website."""

    def _run_with_website(self):
        mock_response = MagicMock()
        mock_response.text = _WEBSITE_HTML_WITH_SOCIALS
        mock_response.ok = True

        with patch("src.pipeline.GooglePlacesCollector") as MockGPC, \
             patch("src.pipeline.WebsiteCollector") as MockWC, \
             patch("src.pipeline.InstagramSignalCollector"), \
             patch("src.pipeline.EmailGuesser"), \
             patch("src.pipeline.ContactDiscovery"):

            mock_places = MagicMock()
            mock_places.search.return_value = [
                {
                    "id": "place_presence_001",
                    "displayName": {"text": "Smile Dental Berlin"},
                    "formattedAddress": "Friedrichstr 10, 10117 Berlin",
                    "businessStatus": "OPERATIONAL",
                    "rating": 4.5,
                    "userRatingCount": 55,
                }
            ]
            mock_places.get_place_details.return_value = _PLACE_WITH_WEBSITE
            MockGPC.return_value = mock_places

            mock_website = MagicMock()
            mock_website.check_website.return_value = (WebsiteStatus.HAS_WEBSITE, mock_response)
            MockWC.return_value = mock_website

            cfg = {**MINIMAL_CONFIG, "enable_email_guesser": False, "enable_contact_discovery": False}
            from src.pipeline import LeadPipeline
            pipeline = LeadPipeline(config=cfg, api_key="test-key")
            return pipeline.run()

    def test_instagram_presence_status_not_unknown(self):
        from src.enums import SocialPresenceStatus
        results = self._run_with_website()
        assert len(results) >= 1
        lead = results[0]
        assert lead.instagram_presence_status != SocialPresenceStatus.UNKNOWN

    def test_instagram_presence_status_found_on_website(self):
        from src.enums import SocialPresenceStatus
        results = self._run_with_website()
        lead = results[0]
        assert lead.instagram_presence_status == SocialPresenceStatus.FOUND_ON_WEBSITE

    def test_facebook_presence_status_found_on_website(self):
        from src.enums import SocialPresenceStatus
        results = self._run_with_website()
        lead = results[0]
        assert lead.facebook_presence_status == SocialPresenceStatus.FOUND_ON_WEBSITE

    def test_instagram_url_populated(self):
        results = self._run_with_website()
        lead = results[0]
        assert lead.instagram_url is not None
        assert "instagram.com" in lead.instagram_url

    def test_social_discovery_method_set(self):
        results = self._run_with_website()
        lead = results[0]
        assert lead.social_discovery_method == "website_html"

    def test_no_website_lead_gets_not_found_status(self):
        """Leads without websites should end up with NOT_FOUND presence statuses."""
        from src.enums import SocialPresenceStatus
        with patch("src.pipeline.GooglePlacesCollector") as MockGPC, \
             patch("src.pipeline.WebsiteCollector") as MockWC, \
             patch("src.pipeline.InstagramSignalCollector"):

            mock_places = MagicMock()
            mock_places.search.return_value = _places_search_result()
            mock_places.get_place_details.return_value = _place_details_result()
            MockGPC.return_value = mock_places

            mock_website = MagicMock()
            mock_website.check_website.return_value = (WebsiteStatus.NO_WEBSITE, None)
            MockWC.return_value = mock_website

            from src.pipeline import LeadPipeline
            pipeline = LeadPipeline(config=MINIMAL_CONFIG, api_key="test-key")
            results = pipeline.run()

            for lead in results:
                assert lead.instagram_presence_status == SocialPresenceStatus.NOT_FOUND
                assert lead.facebook_presence_status == SocialPresenceStatus.NOT_FOUND

    def test_to_json_includes_presence_fields(self):
        results = self._run_with_website()
        for lead in results:
            data = lead.to_json()
            assert "instagram_presence_status" in data
            assert "facebook_presence_status" in data
            assert "social_discovery_method" in data
            assert isinstance(data["instagram_presence_status"], str)
            assert isinstance(data["facebook_presence_status"], str)
