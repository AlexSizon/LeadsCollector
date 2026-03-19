"""Smoke tests for social-discovery-and-contacts change (Group 10)."""
import sys
sys.path.insert(0, ".")

# ── 10.1: CrossSourceMatcher ─────────────────────────────────────────────────
print("=== 10.1  CrossSourceMatcher ===")
from src.models import BusinessLead, SocialCandidate
from src.enums import MatchConfidence
from src.enrichment.cross_source_matcher import CrossSourceMatcher

matcher = CrossSourceMatcher()

leads = [
    BusinessLead(
        company_name="La Bella Cucina", city="Madrid", country="Spain",
        niche="restaurant", phone="+34 91 123 4567",
        website_url="https://labellacucina.es",
    ),
    BusinessLead(
        company_name="Bloom Flowers", city="Amsterdam", country="Netherlands",
        niche="florist", website_url="https://bloomflowers.nl",
    ),
    BusinessLead(
        company_name="Café Central", city="Lisbon", country="Portugal",
        niche="restaurant",
    ),
]

# HIGH: identical name + shared phone
cand_high = SocialCandidate(
    source_platform="instagram", handle_or_page_id="labellacucina",
    display_name="La Bella Cucina", city="Madrid", country="Spain",
    niche="restaurant", website_url="https://labellacucina.es",
    phone="+34 91 123 4567", email=None, social_urls={}, raw_bio="",
)
r = matcher.match(cand_high, leads)
print(f"  HIGH:      confidence={r.confidence.value}, idx={r.matched_index}")
assert r.confidence == MatchConfidence.HIGH, f"Expected HIGH, got {r.confidence}"
assert r.matched_index == 0

# MEDIUM: similar name + same city, no secondary signal
cand_med = SocialCandidate(
    source_platform="facebook", handle_or_page_id="bloom_flowers_ams",
    display_name="Bloom Flowers Amsterdam", city="Amsterdam", country="Netherlands",
    niche="florist", website_url=None,
    phone=None, email=None, social_urls={}, raw_bio="",
)
r2 = matcher.match(cand_med, leads)
print(f"  MEDIUM+:   confidence={r2.confidence.value}, idx={r2.matched_index}")
assert r2.confidence in (MatchConfidence.HIGH, MatchConfidence.MEDIUM), f"Expected MEDIUM+, got {r2.confidence}"

# UNMATCHED: unrelated business
cand_no = SocialCandidate(
    source_platform="instagram", handle_or_page_id="xyz_unrelated",
    display_name="XYZ Unrelated Business", city="Barcelona", country="Spain",
    niche="bakery", website_url=None,
    phone=None, email=None, social_urls={}, raw_bio="",
)
r3 = matcher.match(cand_no, leads)
print(f"  UNMATCHED: confidence={r3.confidence.value}, idx={r3.matched_index}")
assert r3.confidence == MatchConfidence.UNMATCHED

print("  10.1 PASSED\n")


# ── 10.2: ContactDiscovery ───────────────────────────────────────────────────
print("=== 10.2  ContactDiscovery ===")
from src.enrichment.contact_discovery import ContactDiscovery

class _FakeResponse:
    """Minimal mock for requests.Response."""
    def __init__(self, text, url="https://example.com"):
        self.text = text
        self.url = url
    @property
    def status_code(self): return 200

disc = ContactDiscovery()

fake_html = """
<html><body>
  <a href="mailto:info@testbiz.com">Email us</a>
  <a href="tel:+34912345678">Call us</a>
  <a href="https://wa.me/34912345678">WhatsApp</a>
  <a href="https://www.opentable.com/r/testbiz-madrid">Book a table</a>
</body></html>
"""

lead = BusinessLead(company_name="Test Biz", city="Madrid", country="Spain", niche="restaurant")
resp = _FakeResponse(fake_html, "https://testbiz.com")
result = disc.extract(lead, resp)

print(f"  primary_email={result.primary_email}")
print(f"  all_emails={result.all_emails}")
print(f"  all_phones={result.all_phones}")
print(f"  whatsapp_links={result.whatsapp_links}")
print(f"  booking_links={result.booking_links}")

assert result.primary_email == "info@testbiz.com", f"Expected email, got {result.primary_email}"
assert len(result.all_phones) >= 1, "Expected at least 1 phone"
assert len(result.whatsapp_links) >= 1, "Expected WhatsApp link"
assert len(result.booking_links) >= 1, "Expected booking link"
print("  10.2 PASSED\n")


# ── 10.3: InstagramDiscoveryCollector (graceful on network error) ─────────────
print("=== 10.3  InstagramDiscoveryCollector ===")
from src.collectors.instagram_discovery_collector import InstagramDiscoveryCollector

ig = InstagramDiscoveryCollector(request_delay=0)
# Patch network and sleep so backoff doesn't actually wait
import unittest.mock as mock
import requests
with mock.patch("requests.Session.get", side_effect=requests.ConnectionError("simulated")), \
     mock.patch("time.sleep"):
    results = ig.search("coffee shop", "Madrid", "Spain", max_results=5)
print(f"  Graceful result on error: {results}")
assert isinstance(results, list), "Expected list"
assert len(results) == 0, "Expected empty list on network error"
print("  10.3 PASSED\n")


# ── 10.4: FacebookDiscoveryCollector (graceful on network error) ──────────────
print("=== 10.4  FacebookDiscoveryCollector ===")
from src.collectors.facebook_discovery_collector import FacebookDiscoveryCollector

fb = FacebookDiscoveryCollector(request_delay=0)
with mock.patch("requests.Session.get", side_effect=requests.ConnectionError("simulated")), \
     mock.patch("time.sleep"):
    results = fb.search("bakery", "Amsterdam", "Netherlands", max_results=5)
print(f"  Graceful result on error: {results}")
assert isinstance(results, list), "Expected list"
assert len(results) == 0, "Expected empty list on network error"
print("  10.4 PASSED\n")


# ── 10.5 – 10.6: Contactability scoring integration ─────────────────────────
print("=== 10.5 / 10.6  Scoring integration ===")
from src.scoring.contactability import compute_contactability_score
from src.scoring.final_score import compute_final_score

# Lead with no contacts → contactability = 0
lead_no_contact = BusinessLead(company_name="Empty", city="Madrid", country="Spain", niche="restaurant")
score_0 = compute_contactability_score(lead_no_contact)
print(f"  No-contact lead score: {score_0}")
assert score_0 == 0.0, f"Expected 0.0, got {score_0}"

# Lead with email + booking link → contactability > 0
lead_with_contact = BusinessLead(
    company_name="Contact Biz", city="Madrid", country="Spain",
    niche="restaurant",
    primary_email="owner@biz.com",
    all_emails=["owner@biz.com"],
    booking_links=["https://www.opentable.com/r/biz"],
)
score_pos = compute_contactability_score(lead_with_contact)
print(f"  Lead with email+booking score: {score_pos}")
assert score_pos > 0, f"Expected > 0, got {score_pos}"

# Final score accepts contactability param without error
total = compute_final_score(70, 60, 50, 30, score_pos)
print(f"  Final score with contactability: {total}")
assert isinstance(total, float), "Expected float"

print("  10.5 / 10.6 PASSED\n")
print("=== ALL SMOKE TESTS PASSED ===")
