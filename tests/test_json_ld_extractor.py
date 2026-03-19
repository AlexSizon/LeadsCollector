"""Unit tests for src/enrichment/json_ld_extractor.py"""

import json
import pytest
from src.enrichment.json_ld_extractor import extract_from_html


def _wrap(entity: dict) -> str:
    """Wrap a JSON-LD entity dict in minimal HTML."""
    return f'<html><head><script type="application/ld+json">{json.dumps(entity)}</script></head><body></body></html>'


class TestExtractFromHtml:
    def test_no_blocks_returns_empty(self):
        result = extract_from_html("<html><body>No structured data here.</body></html>")
        assert result == {}

    def test_empty_html_returns_empty(self):
        result = extract_from_html("")
        assert result == {}

    def test_malformed_json_skipped_returns_empty(self):
        html = '<html><head><script type="application/ld+json">{ not valid json }</script></head></html>'
        result = extract_from_html(html)
        assert result == {}

    def test_non_local_business_type_returns_empty(self):
        entity = {"@type": "WebSite", "name": "Example", "url": "https://example.com"}
        result = extract_from_html(_wrap(entity))
        assert result == {}

    def test_local_business_phone_and_email(self):
        entity = {
            "@type": "LocalBusiness",
            "name": "Test Cafe",
            "telephone": "+34911234567",
            "email": "info@testcafe.com",
        }
        result = extract_from_html(_wrap(entity))
        assert result["phone"] == "+34911234567"
        assert result["email"] == "info@testcafe.com"
        assert result["name"] == "Test Cafe"

    def test_restaurant_subtype_extracted(self):
        entity = {
            "@type": "Restaurant",
            "name": "Pizza Palace",
            "telephone": "+351912345678",
        }
        result = extract_from_html(_wrap(entity))
        assert result["phone"] == "+351912345678"

    def test_same_as_instagram_classified(self):
        entity = {
            "@type": "LocalBusiness",
            "name": "Beauty Studio",
            "sameAs": [
                "https://www.instagram.com/beautystudio",
                "https://www.facebook.com/beautystudio",
                "https://maps.google.com/beautystudio",
            ],
        }
        result = extract_from_html(_wrap(entity))
        assert any("instagram.com" in u for u in result["social_urls"])
        assert any("facebook.com" in u for u in result["social_urls"])
        # Google Maps is NOT a social domain
        assert not any("google.com" in u for u in result["social_urls"])

    def test_same_as_string_handled(self):
        entity = {
            "@type": "LocalBusiness",
            "name": "Cafe",
            "sameAs": "https://www.instagram.com/mycafe",
        }
        result = extract_from_html(_wrap(entity))
        assert len(result["social_urls"]) == 1
        assert "instagram.com" in result["social_urls"][0]

    def test_postal_address_assembled(self):
        entity = {
            "@type": "LocalBusiness",
            "name": "Dentist Office",
            "address": {
                "@type": "PostalAddress",
                "streetAddress": "Calle Mayor 10",
                "addressLocality": "Madrid",
                "postalCode": "28001",
                "addressCountry": "ES",
            },
        }
        result = extract_from_html(_wrap(entity))
        assert "Calle Mayor 10" in result["address"]
        assert "Madrid" in result["address"]

    def test_address_string_preserved(self):
        entity = {"@type": "LocalBusiness", "name": "Shop", "address": "123 Main St, Porto"}
        result = extract_from_html(_wrap(entity))
        assert result["address"] == "123 Main St, Porto"

    def test_opening_hours_extracted(self):
        entity = {
            "@type": "LocalBusiness",
            "name": "Barbershop",
            "openingHours": ["Mo-Fr 09:00-18:00", "Sa 10:00-16:00"],
        }
        result = extract_from_html(_wrap(entity))
        assert result["opening_hours"] == ["Mo-Fr 09:00-18:00", "Sa 10:00-16:00"]

    def test_multiple_blocks_most_specific_wins(self):
        """Restaurant should beat generic LocalBusiness in same page."""
        generic = {"@type": "LocalBusiness", "name": "Generic", "telephone": "+10000000000"}
        specific = {"@type": "Restaurant", "name": "Specific", "telephone": "+20000000000"}
        html = (
            f'<html><head>'
            f'<script type="application/ld+json">{json.dumps(generic)}</script>'
            f'<script type="application/ld+json">{json.dumps(specific)}</script>'
            f'</head><body></body></html>'
        )
        result = extract_from_html(html)
        assert result["name"] == "Specific"
        assert result["phone"] == "+20000000000"

    def test_malformed_block_followed_by_valid_block(self):
        """A bad block should be skipped; the valid block should still be parsed."""
        valid = {"@type": "LocalBusiness", "name": "Valid Business", "telephone": "+99123456789"}
        html = (
            f'<html><head>'
            f'<script type="application/ld+json">{{ bad json }}</script>'
            f'<script type="application/ld+json">{json.dumps(valid)}</script>'
            f'</head><body></body></html>'
        )
        result = extract_from_html(html)
        assert result["name"] == "Valid Business"

    def test_graph_array_parsed(self):
        """@graph containing a LocalBusiness should be found."""
        graph_doc = {
            "@context": "https://schema.org",
            "@graph": [
                {"@type": "WebSite", "name": "My Site"},
                {"@type": "LocalBusiness", "name": "My Business", "telephone": "+11234567890"},
            ],
        }
        html = f'<html><head><script type="application/ld+json">{json.dumps(graph_doc)}</script></head><body></body></html>'
        result = extract_from_html(html)
        assert result["name"] == "My Business"

    def test_missing_optional_fields_are_none(self):
        entity = {"@type": "LocalBusiness", "name": "Minimal"}
        result = extract_from_html(_wrap(entity))
        assert result["phone"] is None
        assert result["email"] is None
        assert result["address"] is None
        assert result["opening_hours"] is None
        assert result["social_urls"] == []
