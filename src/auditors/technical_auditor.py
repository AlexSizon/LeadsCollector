"""
Technical auditor for SMB websites.

Checks HTTPS enforcement, SSL validity, mobile viewport meta tag,
response time signal, and redirect chain depth. Each check appends
issues and improvement opportunities to the returned lists.
"""

from __future__ import annotations

import ssl
import socket
from typing import List, Optional, Tuple
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup


def audit_technical(
    url: str,
    html: str,
    response: requests.Response,
    timeout: int = 10,
) -> Tuple[List[str], List[str]]:
    """Run technical checks on a fetched website page.

    Parameters
    ----------
    url : str
        The original URL requested.
    html : str
        The response body HTML.
    response : requests.Response
        The HTTP response object (already fetched).
    timeout : int
        Timeout used during the original request (for SSL check reference).

    Returns
    -------
    Tuple[List[str], List[str]]
        (issues_found, improvement_opportunities)
    """
    issues: List[str] = []
    opportunities: List[str] = []
    parsed = urlparse(url)
    final_url = response.url  # After redirects

    # --- HTTPS enforcement ---
    if parsed.scheme == "http":
        final_parsed = urlparse(final_url)
        if final_parsed.scheme != "https":
            issues.append("No HTTPS redirect — site served over plain HTTP")
            opportunities.append("Enable HTTPS with a valid SSL certificate and redirect HTTP → HTTPS")

    # --- SSL validity ---
    final_parsed = urlparse(final_url)
    if final_parsed.scheme == "https":
        hostname = final_parsed.hostname
        if hostname:
            try:
                ctx = ssl.create_default_context()
                with ctx.wrap_socket(
                    socket.create_connection((hostname, 443), timeout=timeout),
                    server_hostname=hostname,
                ):
                    pass
            except ssl.SSLCertVerificationError:
                issues.append("SSL certificate is invalid or expired")
                opportunities.append("Renew or replace the SSL certificate to restore secure browsing")
            except Exception:
                pass  # Network issues — do not flag as SSL problem

    # --- Mobile viewport meta tag ---
    soup = BeautifulSoup(html, "html.parser")
    viewport = soup.find("meta", attrs={"name": lambda v: v and v.lower() == "viewport"})
    if not viewport:
        issues.append("Missing mobile viewport meta tag")
        opportunities.append("Add <meta name='viewport' content='width=device-width, initial-scale=1'> for mobile optimisation")

    # --- Redirect chain depth ---
    redirect_count = len(response.history)
    if redirect_count > 3:
        issues.append(f"Long redirect chain ({redirect_count} redirects) may slow page load")
        opportunities.append("Reduce redirect hops to improve load time and crawlability")

    # --- Response time heuristic ---
    elapsed_ms = response.elapsed.total_seconds() * 1000 if hasattr(response, "elapsed") else None
    if elapsed_ms is not None and elapsed_ms > 3000:
        issues.append(f"Slow server response time ({elapsed_ms:.0f} ms)")
        opportunities.append("Investigate server response time — consider caching, CDN, or hosting upgrade")

    return issues, opportunities
