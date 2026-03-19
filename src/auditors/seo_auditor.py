"""
SEO auditor for SMB websites.

Checks on-page SEO fundamentals: title tag, meta description, H1
heading structure, canonical tag, robots.txt, and local SEO signals.
"""

from __future__ import annotations

from typing import List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


def audit_seo(
    url: str,
    html: str,
    session: Optional[requests.Session] = None,
    timeout: int = 8,
) -> Tuple[List[str], List[str]]:
    """Run SEO checks on a fetched website page.

    Parameters
    ----------
    url : str
        The canonical URL of the page.
    html : str
        The page HTML body.
    session : Optional[requests.Session]
        Optional session for secondary requests (e.g. robots.txt).
    timeout : int
        Timeout for secondary HTTP requests.

    Returns
    -------
    Tuple[List[str], List[str]]
        (issues_found, improvement_opportunities)
    """
    issues: List[str] = []
    opportunities: List[str] = []
    soup = BeautifulSoup(html, "html.parser")

    # --- Title tag ---
    title_tag = soup.find("title")
    title_text = title_tag.get_text(strip=True) if title_tag else ""
    if not title_text:
        issues.append("Missing page title tag")
        opportunities.append("Add a descriptive <title> tag containing primary keywords and business name")
    elif len(title_text) < 10:
        issues.append("Page title is too short (under 10 characters)")
        opportunities.append("Expand the <title> to include service + location (e.g. 'Dentist Berlin | Smile Studio')")

    # --- Meta description ---
    meta_desc = soup.find("meta", attrs={"name": lambda v: v and v.lower() == "description"})
    desc_content = meta_desc.get("content", "").strip() if meta_desc else ""
    if not desc_content:
        issues.append("Missing meta description")
        opportunities.append("Write a 120–160 character meta description summarising services and location")

    # --- H1 heading ---
    h1_tags = soup.find_all("h1")
    if len(h1_tags) == 0:
        issues.append("No H1 heading found on page")
        opportunities.append("Add a single clear <h1> heading that describes the primary service or offering")
    elif len(h1_tags) > 1:
        issues.append(f"Multiple H1 headings found ({len(h1_tags)}) — may confuse search engines")
        opportunities.append("Consolidate to a single <h1> per page to improve heading hierarchy")

    # --- Canonical tag ---
    canonical = soup.find("link", rel=lambda v: v and "canonical" in v)
    if not canonical:
        issues.append("No canonical link tag found")
        opportunities.append("Add a <link rel='canonical'> tag to prevent duplicate content issues")

    # --- robots.txt ---
    parsed = urlparse(url)
    root = f"{parsed.scheme}://{parsed.netloc}"
    robots_url = urljoin(root, "/robots.txt")
    fetcher = session or requests
    try:
        robots_resp = fetcher.get(robots_url, timeout=timeout)
        if robots_resp.status_code != 200:
            issues.append("robots.txt not found or not accessible")
            opportunities.append("Create a robots.txt file to guide search engine crawlers")
    except Exception:
        pass  # Network failure — do not flag

    # --- Local SEO signals ---
    page_text = soup.get_text(separator=" ", strip=True).lower()

    # Address / NAP check (very basic heuristic)
    has_address_hint = any(
        kw in page_text for kw in ["street", "straße", "strasse", "calle", "avenue", "plaza", "platz"]
    )
    if not has_address_hint:
        issues.append("No obvious address / local NAP signal found on homepage")
        opportunities.append("Add your full address (street, city, postal code) to the homepage for local SEO")

    # Schema markup
    schema_scripts = soup.find_all("script", attrs={"type": "application/ld+json"})
    if not schema_scripts:
        issues.append("No structured data (schema.org JSON-LD) detected")
        opportunities.append("Add LocalBusiness or Service schema markup to improve rich snippet eligibility")

    return issues, opportunities
