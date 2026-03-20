"""Email-specific outreach copy generation helpers."""

from __future__ import annotations

from ..enums import OfferType, WebsiteStatus


def derive_offer_type(lead) -> OfferType:
    """Map a lead's website state to the default offer type."""
    current_offer = getattr(lead, "offer_type", None)
    if current_offer:
        try:
            return OfferType(str(current_offer))
        except ValueError:
            pass
    status = getattr(lead, "website_status", WebsiteStatus.UNKNOWN)
    if isinstance(status, str):
        status = WebsiteStatus(status)
    if status in (WebsiteStatus.NO_WEBSITE, WebsiteStatus.SOCIAL_ONLY):
        return OfferType.NEW_WEBSITE
    return OfferType.WEBSITE_IMPROVEMENT


def generate_email_subject(lead) -> str:
    """Generate a low-pressure email subject grounded in observed evidence."""
    offer_type = derive_offer_type(lead)
    company = getattr(lead, "company_name", "your business") or "your business"
    city = getattr(lead, "city", "") or ""
    if offer_type == OfferType.NEW_WEBSITE:
        return f"{company}: simple website idea for {city}".strip()
    if getattr(lead, "website_status", None) == WebsiteStatus.BROKEN_WEBSITE:
        return f"{company}: quick fix for the current site".strip()
    return f"{company}: ideas to improve the current site".strip()


def generate_email_opening(lead) -> str:
    """Generate an opening sentence that references observed evidence only."""
    company = getattr(lead, "company_name", "your business") or "your business"
    reviews = getattr(lead, "google_reviews_count", None)
    status = getattr(lead, "website_status", WebsiteStatus.UNKNOWN)
    if isinstance(status, str):
        status = WebsiteStatus(status)

    if status == WebsiteStatus.NO_WEBSITE and reviews and reviews >= 20:
        return f"I noticed {company} already has visible local demand and {reviews} reviews, but no owned website presence."
    if status == WebsiteStatus.BROKEN_WEBSITE:
        return f"I noticed the current site for {company} appears to be broken or unreachable."
    if status == WebsiteStatus.SOCIAL_ONLY:
        return f"I noticed {company} is visible online mainly through social or directory profiles rather than an owned website."
    issues = getattr(lead, "issues_found", []) or []
    if issues:
        return f"I noticed a few website issues that could make it harder for customers to contact or book with {company}."
    return f"I took a quick look at {company} and saw a few opportunities to make the online customer journey clearer."


def generate_email_cta(lead) -> str:
    """Generate a bounded, non-pressuring CTA."""
    status = getattr(lead, "website_status", WebsiteStatus.UNKNOWN)
    if isinstance(status, str):
        status = WebsiteStatus(status)
    if status in (WebsiteStatus.NO_WEBSITE, WebsiteStatus.SOCIAL_ONLY):
        return "If useful, I can outline a lightweight website structure tailored to this business."
    return "If useful, I can point out the top website fixes worth making first."


def generate_email_body_preview(lead) -> str:
    """Compose a short body preview from opening + short pitch + CTA."""
    opening = generate_email_opening(lead)
    pitch = getattr(lead, "short_pitch", "") or ""
    cta = generate_email_cta(lead)
    parts = [opening]
    if pitch and pitch not in opening:
        parts.append(pitch)
    parts.append(cta)
    return " ".join(p.strip() for p in parts if p and p.strip())
