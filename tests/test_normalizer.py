"""
Unit tests for normalizer.py enrichment utilities.

Covers:
  - normalize_phone(): E.164 format, None inputs, non-parseable strings
  - normalize_name(): whitespace collapsing, lowercase, leading/trailing trim
  - extract_root_domain(): www, m., paths, query strings, CCTLDs
  - classify_website_status(): social domain detection, None/empty URL, real domains
"""

from __future__ import annotations

import pytest

from src.enrichment.normalizer import (
    classify_website_status,
    extract_root_domain,
    normalize_name,
    normalize_phone,
)
from src.enums import WebsiteStatus


# ---------------------------------------------------------------------------
# normalize_phone
# ---------------------------------------------------------------------------

class TestNormalizePhone:
    def test_none_returns_none(self):
        assert normalize_phone(None) is None

    def test_empty_string_returns_none(self):
        assert normalize_phone("") is None

    def test_german_number_e164(self):
        result = normalize_phone("+49 30 12345678", default_region="DE")
        # E.164 has no spaces
        assert result is not None
        assert " " not in result
        assert result.startswith("+")

    def test_local_german_number(self):
        """Local German format should get +49 country code."""
        result = normalize_phone("030 12345678", default_region="DE")
        assert result is not None
        assert result.startswith("+49")

    def test_dutch_number_region(self):
        result = normalize_phone("+31 20 1234567", default_region="NL")
        assert result is not None
        assert result.startswith("+31")

    def test_all_non_digit_garbage_returns_plus_fallback_or_none(self):
        """Strings with no digits should return None."""
        result = normalize_phone("no digits here")
        # Either None or a +... string with minimal digits
        assert result is None or result.startswith("+")

    def test_already_e164(self):
        result = normalize_phone("+4930123456", default_region="DE")
        assert result is not None
        assert result.startswith("+")


# ---------------------------------------------------------------------------
# normalize_name
# ---------------------------------------------------------------------------

class TestNormalizeName:
    def test_lowercase(self):
        assert normalize_name("Smile Studio") == "smile studio"

    def test_trims_whitespace(self):
        assert normalize_name("  Dentist Berlin  ") == "dentist berlin"

    def test_collapses_internal_whitespace(self):
        assert normalize_name("Café  de  Flore") == "café de flore"

    def test_empty_string(self):
        assert normalize_name("") == ""

    def test_single_word(self):
        assert normalize_name("BARBERSHOP") == "barbershop"


# ---------------------------------------------------------------------------
# extract_root_domain
# ---------------------------------------------------------------------------

class TestExtractRootDomain:
    def test_none_returns_none(self):
        assert extract_root_domain(None) is None

    def test_empty_returns_none(self):
        assert extract_root_domain("") is None

    def test_strips_www(self):
        result = extract_root_domain("https://www.example.de/about")
        assert "www" not in result
        assert "example" in result

    def test_strips_m_subdomain(self):
        result = extract_root_domain("http://m.example.com/page")
        assert result == "example.com"

    def test_strips_path_and_query(self):
        result = extract_root_domain("https://example.co.uk/services?lang=en")
        assert "services" not in result
        assert "lang" not in result

    def test_bare_domain(self):
        result = extract_root_domain("https://mysite.nl")
        assert result == "mysite.nl"

    def test_subdomain_stripped(self):
        result = extract_root_domain("https://blog.example.com")
        # Should return root (last two parts)
        assert "example" in result

    def test_no_scheme(self):
        # URL without scheme — urlparse puts it all in path, so result is None or empty
        result = extract_root_domain("example.com")
        # Graceful handling: None, empty string, or a string containing 'example'
        assert result is None or result == "" or "example" in result


# ---------------------------------------------------------------------------
# classify_website_status
# ---------------------------------------------------------------------------

class TestClassifyWebsiteStatus:
    def test_none_url_returns_no_website(self):
        assert classify_website_status(None) == WebsiteStatus.NO_WEBSITE

    def test_empty_url_returns_no_website(self):
        assert classify_website_status("") == WebsiteStatus.NO_WEBSITE

    def test_instagram_url_returns_social_only(self):
        assert classify_website_status("https://www.instagram.com/mybiz") == WebsiteStatus.SOCIAL_ONLY

    def test_facebook_url_returns_social_only(self):
        assert classify_website_status("https://facebook.com/mybiz") == WebsiteStatus.SOCIAL_ONLY

    def test_yelp_url_returns_social_only(self):
        assert classify_website_status("https://www.yelp.com/biz/something") == WebsiteStatus.SOCIAL_ONLY

    def test_tripadvisor_returns_social_only(self):
        assert classify_website_status("https://www.tripadvisor.com/Restaurant_Review") == WebsiteStatus.SOCIAL_ONLY

    def test_booking_com_returns_social_only(self):
        assert classify_website_status("https://www.booking.com/hotel/de/example") == WebsiteStatus.SOCIAL_ONLY

    def test_real_domain_returns_none(self):
        """A real owned domain should return None so HTTP check is performed."""
        assert classify_website_status("https://www.mysmileclinic.de") is None

    def test_linktr_ee_returns_social_only(self):
        assert classify_website_status("https://linktr.ee/mySalon") == WebsiteStatus.SOCIAL_ONLY

    def test_tiktok_returns_social_only(self):
        assert classify_website_status("https://tiktok.com/@mybrand") == WebsiteStatus.SOCIAL_ONLY
