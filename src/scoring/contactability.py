"""
Contactability scorer.

Computes a normalised ``contactability_score`` in [0, 100] that reflects
the breadth and quality of available public contact channels for a lead.

Channel point values (D5 design decision):
  email        = 30
  phone        = 20
  booking_link = 15
  contact_form = 10
  whatsapp     = 10
  messenger    =  5
  instagram_dm =  5 (when instagram_status is FOUND_ACTIVE*)
  facebook_msg =  5 (when facebook_url is set)

Maximum = 100 (capped).
"""

from __future__ import annotations

from ..models import BusinessLead
from ..enums import InstagramStatus


_CHANNEL_POINTS = {
    "email":        30,
    "phone":        20,
    "booking_link": 15,
    "contact_form": 10,
    "whatsapp":     10,
    "messenger":     5,
    "instagram_dm":  5,
    "facebook_msg":  5,
}


def compute_contactability_score(lead: BusinessLead) -> float:
    """Return the contactability score (0–100) for ``lead``."""
    score = 0

    if lead.primary_email or (lead.all_emails and any(lead.all_emails)):
        score += _CHANNEL_POINTS["email"]
    elif getattr(lead, "guessed_email", None):
        # MX-verified guessed email — reduced confidence (+15 vs +30 for scraped)
        # Guard: do not stack with scraped-email branch above
        score += 15

    if lead.primary_phone or (lead.all_phones and any(lead.all_phones)):
        score += _CHANNEL_POINTS["phone"]

    if lead.booking_links:
        score += _CHANNEL_POINTS["booking_link"]

    if lead.contact_form_urls:
        score += _CHANNEL_POINTS["contact_form"]

    if lead.whatsapp_links or lead.whatsapp_url:
        score += _CHANNEL_POINTS["whatsapp"]

    if lead.messenger_links:
        score += _CHANNEL_POINTS["messenger"]

    _ig_active = {InstagramStatus.FOUND_ACTIVE, InstagramStatus.FOUND_ACTIVE_WITH_LINK}
    if lead.instagram_status in _ig_active:
        score += _CHANNEL_POINTS["instagram_dm"]

    if lead.facebook_url:
        score += _CHANNEL_POINTS["facebook_msg"]

    return float(min(score, 100))
