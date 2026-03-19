"""
Unit tests for technical, SEO, and UX auditors.

All tests use fixture HTML strings — no HTTP calls are made.
The technical auditor's SSL and socket operations are patched.
The SEO auditor's robots.txt fetch is mocked.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.auditors.technical_auditor import audit_technical
from src.auditors.seo_auditor import audit_seo
from src.auditors.ux_auditor import audit_ux


# ---------------------------------------------------------------------------
# Helper: build a minimal mock requests.Response
# ---------------------------------------------------------------------------

def _mock_response(
    url: str = "https://example.de/",
    status_code: int = 200,
    elapsed_ms: float = 800,
) -> MagicMock:
    resp = MagicMock()
    resp.url = url
    resp.status_code = status_code
    elapsed = MagicMock()
    elapsed.total_seconds.return_value = elapsed_ms / 1000
    resp.elapsed = elapsed
    return resp


# ---------------------------------------------------------------------------
# Technical auditor
# ---------------------------------------------------------------------------

VIEWPORT_HTML = """<html><head>
<meta name="viewport" content="width=device-width, initial-scale=1">
</head><body>Hello</body></html>"""

NO_VIEWPORT_HTML = """<html><head><title>No Viewport</title></head><body>Hello</body></html>"""

SLOW_RESPONSE_HTML = """<html><head></head><body>slow</body></html>"""


class TestTechnicalAuditor:
    @patch("src.auditors.technical_auditor.ssl.create_default_context")
    def test_no_https_redirect_is_flagged(self, mock_ssl_ctx):
        """An http:// URL that stays on http should flag a missing HTTPS redirect."""
        resp = _mock_response(url="http://example.de/")  # final URL also http
        resp.url = "http://example.de/"
        mock_ssl_ctx.return_value.__enter__ = MagicMock(return_value=None)
        issues, _ = audit_technical("http://example.de/", NO_VIEWPORT_HTML, resp)
        assert any("HTTPS" in i or "HTTP" in i for i in issues)

    @patch("src.auditors.technical_auditor.ssl.create_default_context")
    def test_https_no_redirect_issue(self, mock_ssl_ctx):
        """A URL already on https should NOT flag HTTPS redirect."""
        resp = _mock_response(url="https://example.de/")
        mock_ssl_ctx.return_value.wrap_socket = MagicMock()
        issues, _ = audit_technical("https://example.de/", VIEWPORT_HTML, resp)
        redirect_issues = [i for i in issues if "HTTP" in i and "redirect" in i.lower()]
        assert len(redirect_issues) == 0

    @patch("src.auditors.technical_auditor.ssl.create_default_context")
    def test_missing_viewport_flagged(self, mock_ssl_ctx):
        """Missing viewport meta tag should appear in issues."""
        resp = _mock_response(url="https://example.de/")
        issues, opps = audit_technical("https://example.de/", NO_VIEWPORT_HTML, resp)
        assert any("viewport" in i.lower() for i in issues)

    @patch("src.auditors.technical_auditor.ssl.create_default_context")
    def test_present_viewport_not_flagged(self, mock_ssl_ctx):
        """Present viewport meta tag should not be in issues."""
        resp = _mock_response(url="https://example.de/")
        issues, _ = audit_technical("https://example.de/", VIEWPORT_HTML, resp)
        assert not any("viewport" in i.lower() for i in issues)

    @patch("src.auditors.technical_auditor.ssl.create_default_context")
    @patch("src.auditors.technical_auditor.socket.create_connection")
    def test_ssl_error_flagged(self, mock_conn, mock_ctx):
        """SSLCertVerificationError should add an SSL issue."""
        import ssl
        mock_ctx.return_value.wrap_socket.side_effect = ssl.SSLCertVerificationError("bad cert")
        resp = _mock_response(url="https://example.de/")
        issues, _ = audit_technical("https://example.de/", VIEWPORT_HTML, resp)
        assert any("ssl" in i.lower() or "certificate" in i.lower() for i in issues)

    @patch("src.auditors.technical_auditor.ssl.create_default_context")
    def test_returns_two_lists(self, mock_ctx):
        resp = _mock_response()
        result = audit_technical("https://example.de/", VIEWPORT_HTML, resp)
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        assert isinstance(result[1], list)


# ---------------------------------------------------------------------------
# SEO auditor
# ---------------------------------------------------------------------------

GOOD_SEO_HTML = """<html><head>
<title>Dentist Berlin | Smile Studio</title>
<meta name="description" content="Professional dental care in Berlin. Book your appointment today.">
<link rel="canonical" href="https://smilestudio.de/">
<h1>Best Dentist in Berlin</h1>
</head><body>
<h1>Best Dentist in Berlin</h1>
<p>Visit us at Berliner Straße 12, Berlin 10115.</p>
</body></html>"""

MINIMAL_HTML = """<html><head></head><body><p>Welcome</p></body></html>"""

MULTI_H1_HTML = """<html><head>
<title>Service Page</title>
<meta name="description" content="A decent description here.">
</head><body>
<h1>First Heading</h1>
<h1>Second Heading</h1>
</body></html>"""


class TestSeoAuditor:
    def _robots_ok(self):
        mock_session = MagicMock()
        resp = MagicMock()
        resp.status_code = 200
        mock_session.get.return_value = resp
        return mock_session

    def test_missing_title_flagged(self):
        session = self._robots_ok()
        issues, _ = audit_seo("https://example.de", MINIMAL_HTML, session=session)
        assert any("title" in i.lower() for i in issues)

    def test_missing_meta_description_flagged(self):
        session = self._robots_ok()
        issues, _ = audit_seo("https://example.de", MINIMAL_HTML, session=session)
        assert any("description" in i.lower() for i in issues)

    def test_missing_h1_flagged(self):
        session = self._robots_ok()
        issues, _ = audit_seo("https://example.de", MINIMAL_HTML, session=session)
        assert any("h1" in i.lower() for i in issues)

    def test_multiple_h1_flagged(self):
        session = self._robots_ok()
        issues, _ = audit_seo("https://example.de", MULTI_H1_HTML, session=session)
        assert any("h1" in i.lower() and ("multiple" in i.lower() or "2" in i) for i in issues)

    def test_missing_canonical_flagged(self):
        session = self._robots_ok()
        issues, _ = audit_seo("https://example.de", MINIMAL_HTML, session=session)
        assert any("canonical" in i.lower() for i in issues)

    def test_short_title_flagged(self):
        session = self._robots_ok()
        short_html = """<html><head><title>Hi</title></head><body></body></html>"""
        issues, _ = audit_seo("https://example.de", short_html, session=session)
        assert any("short" in i.lower() or "title" in i.lower() for i in issues)

    def test_good_page_has_fewer_issues(self):
        session = self._robots_ok()
        issues, _ = audit_seo("https://example.de", GOOD_SEO_HTML, session=session)
        bad_issues, _ = audit_seo("https://example.de", MINIMAL_HTML, session=session)
        assert len(issues) <= len(bad_issues)

    def test_returns_two_lists(self):
        session = self._robots_ok()
        result = audit_seo("https://example.de", MINIMAL_HTML, session=session)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_robots_not_found_flagged(self):
        mock_session = MagicMock()
        resp = MagicMock()
        resp.status_code = 404
        mock_session.get.return_value = resp
        issues, _ = audit_seo("https://example.de", GOOD_SEO_HTML, session=mock_session)
        assert any("robots" in i.lower() for i in issues)


# ---------------------------------------------------------------------------
# UX auditor
# ---------------------------------------------------------------------------

FULL_UX_HTML = """<html><body>
<a href="tel:+493012345678">Call us</a>
<a href="#booking"><button>Book an appointment</button></a>
<form action="/contact" method="post"><input type="text"><button type="submit">Send</button></form>
<a href="https://wa.me/493012345678">WhatsApp us</a>
<p>Our customers love us. 5 stars reviews testimonials.</p>
</body></html>"""

EMPTY_UX_HTML = """<html><body><p>Welcome to our website.</p></body></html>"""

TEL_LINK_HTML = """<html><body>
<a href="tel:+4930999888">Call now</a>
<p>thank you for visiting</p>
</body></html>"""


class TestUxAuditor:
    def test_no_cta_flagged(self):
        issues, _ = audit_ux(EMPTY_UX_HTML)
        assert any("cta" in i.lower() or "call-to-action" in i.lower() for i in issues)

    def test_no_tel_link_flagged(self):
        issues, _ = audit_ux(EMPTY_UX_HTML)
        assert any("tel" in i.lower() or "call" in i.lower() for i in issues)

    def test_no_form_flagged(self):
        issues, _ = audit_ux(EMPTY_UX_HTML)
        assert any("form" in i.lower() for i in issues)

    def test_tel_link_present_not_flagged(self):
        issues, _ = audit_ux(TEL_LINK_HTML)
        assert not any("tel" in i.lower() for i in issues)

    def test_full_ux_minimal_issues(self):
        issues, _ = audit_ux(FULL_UX_HTML)
        # A well-optimised page should have zero or very few issues
        assert len(issues) <= 1

    def test_whatsapp_link_removes_opportunity(self):
        issues, opps = audit_ux(FULL_UX_HTML)
        whatsapp_opps = [o for o in opps if "whatsapp" in o.lower() or "messaging" in o.lower()]
        assert len(whatsapp_opps) == 0

    def test_booking_cta_keyword_detected(self):
        html = """<html><body><a href="/book">Book now</a></body></html>"""
        issues, _ = audit_ux(html)
        assert not any("cta" in i.lower() for i in issues)

    def test_returns_two_lists(self):
        result = audit_ux(EMPTY_UX_HTML)
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        assert isinstance(result[1], list)
