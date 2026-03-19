"""
Unit tests for Instagram signal collection and scoring.

Covers:
  - extract_handle_from_html(): handle discovery from page HTML
  - analyze_handle(): HTTP status → InstagramStatus classification
    (404 → NOT_FOUND, 500 → UNKNOWN, 429 → UNKNOWN)
  - analyze_handle(): post-count parsing → FOUND_ACTIVE / FOUND_INACTIVE
  - compute_instagram_signal(): score per status (including UNKNOWN=30)
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.collectors.instagram_signal_collector import InstagramSignalCollector
from src.enums import InstagramStatus
from src.scoring.instagram_signal import compute_instagram_signal


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _mock_resp(status_code: int, text: str = "") -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    return resp


# ---------------------------------------------------------------------------
# extract_handle_from_html
# ---------------------------------------------------------------------------

class TestExtractHandleFromHtml:
    def setup_method(self):
        self.collector = InstagramSignalCollector()

    def test_finds_handle_in_href(self):
        html = '<html><body><a href="https://www.instagram.com/myshop_berlin/">Follow us</a></body></html>'
        handle = self.collector.extract_handle_from_html(html)
        assert handle == "myshop_berlin"

    def test_returns_none_when_no_instagram_link(self):
        html = '<html><body><a href="https://example.com">Home</a></body></html>'
        assert self.collector.extract_handle_from_html(html) is None

    def test_skips_generic_paths(self):
        """Paths like /p/, /explore, /reel should not be returned as handles."""
        for path in ["p", "explore", "reel", "stories", "tv"]:
            html = f'<html><body><a href="https://www.instagram.com/{path}/12345">Content</a></body></html>'
            assert self.collector.extract_handle_from_html(html) is None

    def test_handle_case_insensitive_instagram_domain(self):
        html = '<html><body><a href="https://INSTAGRAM.COM/MyHandle/">IG</a></body></html>'
        handle = self.collector.extract_handle_from_html(html)
        assert handle == "MyHandle"

    def test_empty_html(self):
        assert self.collector.extract_handle_from_html("") is None

    def test_non_instagram_link_ignored(self):
        html = '<html><body><a href="https://facebook.com/mybiz">FB</a></body></html>'
        assert self.collector.extract_handle_from_html(html) is None


# ---------------------------------------------------------------------------
# analyze_handle
# ---------------------------------------------------------------------------

class TestAnalyzeHandle:
    def setup_method(self):
        self.collector = InstagramSignalCollector()

    def test_404_returns_not_found(self):
        self.collector.session.get = MagicMock(return_value=_mock_resp(404))
        status = self.collector.analyze_handle("ghosthandle")
        assert status == InstagramStatus.NOT_FOUND

    def test_500_returns_unknown(self):
        self.collector.session.get = MagicMock(return_value=_mock_resp(500))
        status = self.collector.analyze_handle("errorhandle")
        assert status == InstagramStatus.UNKNOWN

    def test_429_returns_unknown(self):
        self.collector.session.get = MagicMock(return_value=_mock_resp(429))
        status = self.collector.analyze_handle("ratelimited")
        assert status == InstagramStatus.UNKNOWN

    def test_network_error_returns_unknown(self):
        self.collector.session.get = MagicMock(side_effect=ConnectionError("timeout"))
        status = self.collector.analyze_handle("offline")
        assert status == InstagramStatus.UNKNOWN

    def test_active_profile_with_enough_posts(self):
        html = '"edge_owner_to_timeline_media":{"count":25}'
        self.collector.session.get = MagicMock(return_value=_mock_resp(200, html))
        status = self.collector.analyze_handle("activeuser")
        assert status == InstagramStatus.FOUND_ACTIVE

    def test_active_with_link_in_bio(self):
        html = '"edge_owner_to_timeline_media":{"count":50} rel="nofollow" '
        self.collector.session.get = MagicMock(return_value=_mock_resp(200, html))
        status = self.collector.analyze_handle("linkeduser")
        assert status == InstagramStatus.FOUND_ACTIVE_WITH_LINK

    def test_inactive_profile_low_posts(self):
        html = '"edge_owner_to_timeline_media":{"count":3}'
        self.collector.session.get = MagicMock(return_value=_mock_resp(200, html))
        status = self.collector.analyze_handle("inactiveuser")
        assert status == InstagramStatus.FOUND_INACTIVE

    def test_post_count_from_text_pattern(self):
        """Instagram embeds post count as 'XX Posts' in some pages."""
        html = "<html><head><title>15 Posts - @mybiz on Instagram</title></head></html>"
        self.collector.session.get = MagicMock(return_value=_mock_resp(200, html))
        status = self.collector.analyze_handle("countbiz")
        assert status in (InstagramStatus.FOUND_ACTIVE, InstagramStatus.FOUND_INACTIVE)


# ---------------------------------------------------------------------------
# compute_instagram_signal scoring
# ---------------------------------------------------------------------------

class TestComputeInstagramSignal:
    def test_not_found_score_zero(self):
        assert compute_instagram_signal(InstagramStatus.NOT_FOUND) == 0.0

    def test_found_inactive_score_20(self):
        assert compute_instagram_signal(InstagramStatus.FOUND_INACTIVE) == 20.0

    def test_found_active_score_60(self):
        assert compute_instagram_signal(InstagramStatus.FOUND_ACTIVE) == 60.0

    def test_found_active_with_link_score_80(self):
        assert compute_instagram_signal(InstagramStatus.FOUND_ACTIVE_WITH_LINK) == 80.0

    def test_unknown_score_30_not_zero(self):
        """UNKNOWN should return 30 (neutral), not 0 (punitive)."""
        score = compute_instagram_signal(InstagramStatus.UNKNOWN)
        assert score == 30.0

    def test_all_scores_in_range(self):
        for status in InstagramStatus:
            score = compute_instagram_signal(status)
            assert 0.0 <= score <= 100.0
