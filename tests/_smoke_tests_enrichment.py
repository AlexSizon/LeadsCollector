"""
Smoke tests for max-contact-enrichment features.

Tasks covered:
  8.1 - EmailGuesser: known domain + invalid domain
  8.2 - TripAdvisorCollector: niche guard + network error graceful handling
  8.3 - contactability_score with guessed_email field
  8.4 - Full pipeline smoke (integration, skipped if no network)
  8.5 - Viewer renders Reachable Leads tab (import check)

Run:
    pytest tests/_smoke_tests_enrichment.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# ---------------------------------------------------------------------------
# 8.1  EmailGuesser
# ---------------------------------------------------------------------------

class TestEmailGuesser:
    """Smoke-test EmailGuesser._check_mx and .guess()."""

    def test_known_domain_returns_email(self):
        """google.com has MX records → guess() returns a non-None address."""
        from src.enrichment.email_guesser import EmailGuesser

        guesser = EmailGuesser()
        result = guesser.guess("https://www.google.com", niche="tech")
        # Should return something like "info@google.com"
        assert result is not None
        assert "@google.com" in result

    def test_invalid_domain_returns_none(self):
        """A clearly bogus domain has no MX → guess() returns None."""
        from src.enrichment.email_guesser import EmailGuesser

        guesser = EmailGuesser()
        result = guesser.guess("https://this-domain-should-not-exist-xyz-999.invalid")
        assert result is None

    def test_empty_url_returns_none(self):
        from src.enrichment.email_guesser import EmailGuesser

        guesser = EmailGuesser()
        assert guesser.guess("") is None
        assert guesser.guess(None) is None  # type: ignore[arg-type]

    def test_hospitality_niche_uses_reservas_prefix(self):
        """For a restaurant niche, the guessed prefix should be 'reservas' or 'bookings'."""
        from src.enrichment.email_guesser import EmailGuesser

        guesser = EmailGuesser()
        # Patch _check_mx to return True so we can test prefix logic
        with patch.object(guesser, "_check_mx", return_value=True):
            result = guesser.guess("https://www.example.com", niche="restaurant")
        assert result is not None
        prefix = result.split("@")[0]
        assert prefix in ("reservas", "bookings"), f"Expected reservas/bookings prefix, got: {prefix}"

    def test_non_hospitality_niche_uses_info_prefix(self):
        """For a non-hospitality niche, the first prefix should be 'info'."""
        from src.enrichment.email_guesser import EmailGuesser

        guesser = EmailGuesser()
        with patch.object(guesser, "_check_mx", return_value=True):
            result = guesser.guess("https://www.example.com", niche="dentist")
        assert result is not None
        prefix = result.split("@")[0]
        assert prefix == "info", f"Expected 'info' prefix, got: {prefix}"

    def test_extract_domain(self):
        from src.enrichment.email_guesser import EmailGuesser

        assert EmailGuesser._extract_domain("https://www.example.com/path?q=1") == "example.com"
        assert EmailGuesser._extract_domain("http://shop.example.co.uk:8080/") == "shop.example.co.uk"
        assert EmailGuesser._extract_domain("") is None


# ---------------------------------------------------------------------------
# 8.2  TripAdvisorCollector
# ---------------------------------------------------------------------------

class TestTripAdvisorCollector:
    """Smoke-test TripAdvisorCollector niche guard and error handling."""

    def test_non_hospitality_niche_returns_empty_no_http(self):
        """Non-hospitality niche must return [] with zero network calls."""
        from src.collectors.tripadvisor_collector import TripAdvisorCollector

        collector = TripAdvisorCollector()
        with patch.object(collector._session, "get") as mock_get:
            result = collector.search(niche="dentist", city="Madrid", country="Spain")
        assert result == []
        mock_get.assert_not_called()

    def test_hospitality_niche_graceful_on_network_error(self):
        """Network error during Google search must return [] without raising."""
        from src.collectors.tripadvisor_collector import TripAdvisorCollector
        import requests

        collector = TripAdvisorCollector()
        with patch.object(
            collector._session,
            "get",
            side_effect=requests.ConnectionError("network error"),
        ):
            result = collector.search(niche="restaurant", city="Madrid", country="Spain")
        assert result == []

    def test_non_hospitality_niches_all_blocked(self):
        """Verify the full set of non-hospitality niches returns [] immediately."""
        from src.collectors.tripadvisor_collector import TripAdvisorCollector, HOSPITALITY_NICHES

        collector = TripAdvisorCollector()
        non_hospitality = ["dentist", "beauty salon", "florist", "boutique", "pet shop"]
        for niche in non_hospitality:
            assert niche.lower() not in HOSPITALITY_NICHES
            with patch.object(collector._session, "get") as mock_get:
                result = collector.search(niche=niche, city="Madrid")
            assert result == [], f"Expected [] for non-hospitality niche: {niche}"
            mock_get.assert_not_called()


# ---------------------------------------------------------------------------
# 8.3  Contactability score with guessed_email
# ---------------------------------------------------------------------------

class TestContactabilityWithGuessedEmail:
    """Smoke-test contactability scoring for guessed_email field."""

    def _make_lead(self, **kwargs):
        from src.models import BusinessLead
        return BusinessLead(
            company_name="Test Co",
            niche="restaurant",
            country="Spain",
            city="Madrid",
            **kwargs
        )

    def test_guessed_email_scores_15_when_no_other_email(self):
        """guessed_email only → contactability score should be 15."""
        from src.scoring.contactability import compute_contactability_score

        lead = self._make_lead(guessed_email="info@example.com")
        score = compute_contactability_score(lead)
        assert score == 15.0, f"Expected 15.0, got {score}"

    def test_guessed_email_does_not_stack_with_scraped_email(self):
        """When primary_email is set, guessed_email should not add extra points."""
        from src.scoring.contactability import compute_contactability_score

        lead_scraped_only = self._make_lead(primary_email="real@example.com")
        lead_both = self._make_lead(
            primary_email="real@example.com",
            guessed_email="info@example.com",
        )
        score_scraped = compute_contactability_score(lead_scraped_only)
        score_both    = compute_contactability_score(lead_both)
        # guessed_email must not add to points when primary_email is present
        assert score_scraped == score_both, (
            f"Score should not change with guessed_email when primary_email is set. "
            f"scraped={score_scraped}, both={score_both}"
        )
        # Scraped email alone should give 30 pts
        assert score_scraped == 30.0, f"Expected 30.0 for scraped email only, got {score_scraped}"

    def test_zero_channels_returns_zero(self):
        """Lead with no contact channels should have score 0."""
        from src.scoring.contactability import compute_contactability_score

        lead = self._make_lead()
        assert compute_contactability_score(lead) == 0.0

    def test_guessed_email_plus_phone(self):
        """guessed_email + phone → 15 + 20 = 35."""
        from src.scoring.contactability import compute_contactability_score

        lead = self._make_lead(guessed_email="info@example.com", primary_phone="+34 600 000 001")
        score = compute_contactability_score(lead)
        assert score == 35.0, f"Expected 35.0, got {score}"


# ---------------------------------------------------------------------------
# 8.4  Full pipeline smoke (integration — skipped when no output data)
# ---------------------------------------------------------------------------

class TestPipelineIntegration:
    """Basic integration checks on leads data if available."""

    def test_guessed_email_in_json_schema(self):
        """BusinessLead.to_json() must include guessed_email key."""
        from src.models import BusinessLead

        lead = BusinessLead(
            company_name="Test",
            niche="restaurant",
            country="Spain",
            city="Madrid",
            guessed_email="info@example.com",
        )
        data = lead.to_json()
        assert "guessed_email" in data
        assert data["guessed_email"] == "info@example.com"

    def test_guessed_email_none_in_json_schema(self):
        """BusinessLead.to_json() with no guessed_email must return None for the key."""
        from src.models import BusinessLead

        lead = BusinessLead(
            company_name="Test",
            niche="restaurant",
            country="Spain",
            city="Madrid",
        )
        data = lead.to_json()
        assert "guessed_email" in data
        assert data["guessed_email"] is None

    @pytest.mark.skipif(
        not (ROOT / "output" / "leads.json").exists(),
        reason="No pipeline output available — run the pipeline first",
    )
    def test_existing_leads_contactability_positive(self):
        """If leads.json exists, some leads should have contactability > 0."""
        import json

        path = ROOT / "output" / "leads.json"
        data = json.loads(path.read_text("utf-8"))
        assert len(data) > 0, "leads.json should be non-empty"
        positive = [l for l in data if l.get("contactability_score", 0) > 0]
        # At least some leads should be reachable
        assert len(positive) > 0, "Expected at least one lead with contactability_score > 0"


# ---------------------------------------------------------------------------
# 8.5  Viewer smoke (import + Reachable Leads tab logic)
# ---------------------------------------------------------------------------

class TestViewerSmoke:
    """Verify viewer/app.py can be imported and the reachable tab helper exists."""

    def test_viewer_imports_without_error(self):
        """viewer/app.py must be importable (no syntax errors)."""
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "viewer_app", ROOT / "viewer" / "app.py"
        )
        mod = importlib.util.module_from_spec(spec)
        # Don't execute it (requires Streamlit context), just check compile
        # spec.loader.exec_module(mod)  # would require st context
        # Instead just compile:
        source = (ROOT / "viewer" / "app.py").read_text("utf-8")
        compile(source, "viewer/app.py", "exec")  # raises SyntaxError if broken

    def test_reachable_tab_function_exists(self):
        """_render_reachable_tab must be defined in viewer/app.py."""
        source = (ROOT / "viewer" / "app.py").read_text("utf-8")
        assert "_render_reachable_tab" in source

    def test_guessed_email_indicator_in_viewer(self):
        """Viewer must contain the guessed email MX-verified indicator string."""
        source = (ROOT / "viewer" / "app.py").read_text("utf-8")
        assert "MX verified, not scraped" in source
