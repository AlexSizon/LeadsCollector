"""
UX / CRO auditor for SMB websites.

Checks conversion-critical signals: CTAs, click-to-call, contact or
booking forms, WhatsApp / messaging links, and trust blocks.
"""

from __future__ import annotations

import re
from typing import List, Tuple

from bs4 import BeautifulSoup


# Keywords that indicate a conversion-oriented CTA (multi-language)
CTA_KEYWORDS = [
    # English
    "book", "reserve", "appointment", "contact", "schedule", "get a quote",
    # German
    "buchen", "termin", "anfragen", "anmelden", "kontakt",
    # Spanish
    "reservar", "cita", "contactar", "solicitar",
    # Dutch
    "boeken", "afspraak", "contact",
]

BOOKING_KEYWORDS = [
    "book", "booking", "reserve", "appointment", "buchen", "buchung",
    "termin", "reservar", "reserva", "cita", "afspraak", "boeken",
]


def audit_ux(html: str) -> Tuple[List[str], List[str]]:
    """Run UX and CRO checks on a fetched website page.

    Parameters
    ----------
    html : str
        The page HTML body.

    Returns
    -------
    Tuple[List[str], List[str]]
        (issues_found, improvement_opportunities)
    """
    issues: List[str] = []
    opportunities: List[str] = []
    soup = BeautifulSoup(html, "html.parser")
    page_text = soup.get_text(separator=" ", strip=True).lower()

    # --- CTA detection ---
    cta_found = False
    for tag in soup.find_all(["a", "button"]):
        tag_text = tag.get_text(strip=True).lower()
        if any(tag_text.startswith(kw) or kw in tag_text for kw in CTA_KEYWORDS):
            cta_found = True
            break
    if not cta_found:
        issues.append("No clear call-to-action (CTA) found on homepage")
        opportunities.append("Add a prominent CTA button for booking, contacting, or enquiring")

    # --- Click-to-call link ---
    tel_links = soup.find_all("a", href=re.compile(r"^tel:", re.I))
    if not tel_links:
        issues.append("No click-to-call (tel:) link found")
        opportunities.append("Add a clickable phone number (href='tel:+...') to lower contact friction on mobile")

    # --- Contact or booking form ---
    forms = soup.find_all("form")
    if not forms:
        issues.append("No contact or booking form found on page")
        opportunities.append("Add a contact or appointment-request form to capture leads directly")

    # --- WhatsApp / messaging CTA ---
    whatsapp_link = soup.find("a", href=re.compile(r"wa\.me|whatsapp\.com", re.I))
    whatsapp_text = "whatsapp" in page_text or "telegram" in page_text
    if not whatsapp_link and not whatsapp_text:
        opportunities.append("Consider adding a WhatsApp or messaging link for lower-friction mobile contact")

    # --- Testimonials / reviews block ---
    review_signals = ["testimonial", "review", "bewertung", "reseña", "rezension", "beoordeling"]
    has_reviews = any(s in page_text for s in review_signals)
    if not has_reviews:
        issues.append("No visible testimonials or review section found")
        opportunities.append("Add a customer testimonials or reviews section to build trust")

    # --- Booking-keyword presence check ---
    has_booking = any(kw in page_text for kw in BOOKING_KEYWORDS)
    if not has_booking:
        opportunities.append("Consider making booking or appointment scheduling more prominent in the page copy")

    return issues, opportunities
