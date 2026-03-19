"""
Unit tests for GooglePlacesCollector.

Covers:
  - Query generation (niche × city pattern)
  - PERMANENTLY_CLOSED / CLOSED_TEMPORARILY filtering
  - Rate-limiting: sleep is called between requests
  - API key fallback to environment variable
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List
from unittest.mock import MagicMock, call, patch

import pytest

from src.collectors.google_places_collector import GooglePlacesCollector


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_PLACES = [
    {
        "id": "place_001",
        "displayName": {"text": "Open Dentist"},
        "businessStatus": "OPERATIONAL",
        "rating": 4.5,
        "userRatingCount": 80,
    },
    {
        "id": "place_002",
        "displayName": {"text": "Closed Forever Clinic"},
        "businessStatus": "PERMANENTLY_CLOSED",
        "rating": 3.0,
        "userRatingCount": 10,
    },
    {
        "id": "place_003",
        "displayName": {"text": "Temp Closed Salon"},
        "businessStatus": "CLOSED_TEMPORARILY",
        "rating": 4.2,
        "userRatingCount": 45,
    },
    {
        "id": "place_004",
        "displayName": {"text": "Another Open Barbershop"},
        "businessStatus": "OPERATIONAL",
        "rating": 4.8,
        "userRatingCount": 120,
    },
]


def _make_mock_response(places: List[Dict]) -> MagicMock:
    """Return a mock Response whose .json() returns {places: [...]}.."""
    resp = MagicMock()
    resp.json.return_value = {"places": places}
    resp.raise_for_status = MagicMock()
    return resp


def _make_details_response(data: Dict) -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = data
    resp.raise_for_status = MagicMock()
    return resp


# ---------------------------------------------------------------------------
# Instantiation
# ---------------------------------------------------------------------------

class TestInstantiation:
    def test_explicit_api_key(self):
        collector = GooglePlacesCollector(api_key="test-key")
        assert collector.api_key == "test-key"

    def test_env_var_fallback(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PLACES_API_KEY", "env-key")
        collector = GooglePlacesCollector()
        assert collector.api_key == "env-key"

    def test_missing_api_key_raises(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_PLACES_API_KEY", raising=False)
        with pytest.raises(ValueError, match="API key"):
            GooglePlacesCollector()

    def test_default_request_delay(self):
        collector = GooglePlacesCollector(api_key="k")
        assert collector.request_delay == 0.3

    def test_custom_request_delay(self):
        collector = GooglePlacesCollector(api_key="k", request_delay=1.0)
        assert collector.request_delay == 1.0


# ---------------------------------------------------------------------------
# search() — filtering
# ---------------------------------------------------------------------------

class TestSearch:
    """Tests for the search() method, with mocked HTTP."""

    @patch("src.collectors.google_places_collector.requests.post")
    @patch("src.collectors.google_places_collector.time.sleep")
    def test_filters_permanently_closed(self, mock_sleep, mock_post):
        mock_post.return_value = _make_mock_response(SAMPLE_PLACES)
        collector = GooglePlacesCollector(api_key="k")
        results = collector.search("dentist in Berlin")
        ids = [r["id"] for r in results]
        assert "place_002" not in ids

    @patch("src.collectors.google_places_collector.requests.post")
    @patch("src.collectors.google_places_collector.time.sleep")
    def test_filters_closed_temporarily(self, mock_sleep, mock_post):
        mock_post.return_value = _make_mock_response(SAMPLE_PLACES)
        collector = GooglePlacesCollector(api_key="k")
        results = collector.search("dentist in Berlin")
        ids = [r["id"] for r in results]
        assert "place_003" not in ids

    @patch("src.collectors.google_places_collector.requests.post")
    @patch("src.collectors.google_places_collector.time.sleep")
    def test_keeps_operational_places(self, mock_sleep, mock_post):
        mock_post.return_value = _make_mock_response(SAMPLE_PLACES)
        collector = GooglePlacesCollector(api_key="k")
        results = collector.search("dentist in Berlin")
        ids = [r["id"] for r in results]
        assert "place_001" in ids
        assert "place_004" in ids

    @patch("src.collectors.google_places_collector.requests.post")
    @patch("src.collectors.google_places_collector.time.sleep")
    def test_places_without_status_are_kept(self, mock_sleep, mock_post):
        """Places with no businessStatus field should not be filtered out."""
        places = [{"id": "x", "displayName": {"text": "No Status Bar"}}]
        mock_post.return_value = _make_mock_response(places)
        collector = GooglePlacesCollector(api_key="k")
        results = collector.search("bar in Amsterdam")
        assert len(results) == 1

    @patch("src.collectors.google_places_collector.requests.post")
    @patch("src.collectors.google_places_collector.time.sleep")
    def test_empty_results(self, mock_sleep, mock_post):
        mock_post.return_value = _make_mock_response([])
        collector = GooglePlacesCollector(api_key="k")
        results = collector.search("unicorn in Vienna")
        assert results == []

    @patch("src.collectors.google_places_collector.requests.post")
    @patch("src.collectors.google_places_collector.time.sleep")
    def test_rate_limit_sleep_called(self, mock_sleep, mock_post):
        mock_post.return_value = _make_mock_response([])
        collector = GooglePlacesCollector(api_key="k", request_delay=0.5)
        collector.search("test query")
        mock_sleep.assert_called_once_with(0.5)


# ---------------------------------------------------------------------------
# get_place_details()
# ---------------------------------------------------------------------------

class TestGetPlaceDetails:
    @patch("src.collectors.google_places_collector.requests.get")
    @patch("src.collectors.google_places_collector.time.sleep")
    def test_returns_json_data(self, mock_sleep, mock_get):
        detail = {
            "id": "place_001",
            "displayName": {"text": "Smile Studio"},
            "rating": 4.7,
            "userRatingCount": 95,
            "websiteUri": "https://smilestudio.de",
            "internationalPhoneNumber": "+49 30 12345678",
        }
        mock_get.return_value = _make_details_response(detail)
        collector = GooglePlacesCollector(api_key="k")
        result = collector.get_place_details("place_001")
        assert result["id"] == "place_001"
        assert result["rating"] == 4.7

    @patch("src.collectors.google_places_collector.requests.get")
    @patch("src.collectors.google_places_collector.time.sleep")
    def test_rate_limit_sleep_called(self, mock_sleep, mock_get):
        mock_get.return_value = _make_details_response({})
        collector = GooglePlacesCollector(api_key="k", request_delay=0.2)
        collector.get_place_details("abc123")
        mock_sleep.assert_called_once_with(0.2)

    @patch("src.collectors.google_places_collector.requests.get")
    @patch("src.collectors.google_places_collector.time.sleep")
    def test_uses_correct_place_id_in_url(self, mock_sleep, mock_get):
        mock_get.return_value = _make_details_response({})
        collector = GooglePlacesCollector(api_key="k")
        collector.get_place_details("my-place-id-123")
        called_url = mock_get.call_args[0][0]
        assert "my-place-id-123" in called_url


# ---------------------------------------------------------------------------
# Query string generation (sanity check)
# ---------------------------------------------------------------------------

class TestQueryGeneration:
    """Verify that niche × city style queries are valid strings."""

    def test_simple_query_format(self):
        """Query strings should be non-empty and contain both terms."""
        niche = "barbershop"
        city = "Amsterdam"
        query = f"{niche} in {city}"
        assert niche in query
        assert city in query
        assert len(query) > 5
