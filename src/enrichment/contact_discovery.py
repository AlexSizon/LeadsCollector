"""
Contact discovery module.

Extracts all publicly available contact information for a business from:
1. Already-fetched website HTML (main page, reuses cached response)
2. A contact sub-page (/contact, /about, etc.) — ONE extra request if needed
3. Social URLs already stored on the BusinessLead

Rules:
- Never invents/guesses contact data
- Normalises and deduplicates all values
- Selects primary contact per type based on priority ordering
- Booking-heavy niches: booking link elevated above contact form

Design reference: D4 (reuse cached HTML), D5 (contactability scoring).
"""

from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from ..models import BusinessLead, ContactResult
from ..enrichment.normalizer import normalize_phone as _normalize_phone

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Country name → ISO 3166-1 alpha-2 region code (for phone normalization)
# ---------------------------------------------------------------------------
_COUNTRY_TO_REGION: dict = {
    "spain": "ES",
    "netherlands": "NL",
    "portugal": "PT",
    "germany": "DE",
    "france": "FR",
    "italy": "IT",
    "belgium": "BE",
    "austria": "AT",
    "switzerland": "CH",
    "united kingdom": "GB",
    "uk": "GB",
    "usa": "US",
    "united states": "US",
    "poland": "PL",
    "denmark": "DK",
    "sweden": "SE",
    "norway": "NO",
    "finland": "FI",
    "ireland": "IE",
    "greece": "GR",
    "czech republic": "CZ",
    "hungary": "HU",
    "romania": "RO",
    "brazil": "BR",
    "mexico": "MX",
    "argentina": "AR",
    "colombia": "CO",
    "chile": "CL",
}

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Booking-heavy niches where a booking link is preferred over a contact form
_BOOKING_HEAVY_NICHES = frozenset({
    "restaurant", "beauty salon", "barbershop", "spa", "dentist",
    "hair salon", "nail salon", "yoga studio", "gym", "clinic",
    "hotel", "hostel", "guesthouse",
})

# Known booking platform domains
_BOOKING_DOMAINS = frozenset({
    "opentable.com", "thefork.com", "booksy.com", "calendly.com",
    "reservio.com", "mindbody.io", "fresha.com", "treatwell.co.uk",
    "treatwell.es", "treatwell.nl", "vagaro.com", "setmore.com",
    "acuityscheduling.com", "simplybook.me", "planyo.com",
    "resy.com", "yelp.com", "tripadvisor.com",
})

# Path segments that indicate a booking/reservation page
_BOOKING_PATH_HINTS = frozenset({
    "booking", "reservations", "reservation", "appointments",
    "appointment", "book", "reserve", "buchen", "reservar", "boeken",
})

# Path segments that indicate a contact page
_CONTACT_PATH_HINTS = frozenset({
    "contact", "kontakt", "contacto", "contacte", "contact-us",
    "contactez", "contacte-nous", "get-in-touch", "reach-us",
})

# WhatsApp / Messenger link patterns
_WHATSAPP_RE = re.compile(
    r"https?://(?:wa\.me|api\.whatsapp\.com/send|web\.whatsapp\.com/send|"
    r"chat\.whatsapp\.com)/[^\s\"'<>]{2,}",
    re.I,
)
_MESSENGER_RE = re.compile(
    r"https?://(?:m\.me|messenger\.com/t)/[A-Za-z0-9._\-]{1,}",
    re.I,
)

_EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
    re.I,
)
_TEL_RE = re.compile(
    r"tel:([+\d\s\(\)\-\.]{5,})",
    re.I,
)
_PHONE_TEXT_RE = re.compile(
    r"(?<!\w)(?:\+?\d{1,3}[\s\-\.]?)?(?:\(?\d{2,4}\)?[\s\-\.]?)(?:\d{3,4}[\s\-\.]?){2,}\d{2,}(?!\w)",
)

# Email false-positive filters
_EMAIL_SKIP_DOMAINS = frozenset({
    "example.", "test.", "sentry.", "domain.", "email.",
    "placeholder.", "dummy.",
})
_EMAIL_SKIP_EXTENSIONS = (".png", ".jpg", ".gif", ".css", ".js", ".svg", ".webp")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clean_email(raw: str) -> Optional[str]:
    """Normalise and validate an email address, return None if invalid."""
    email = raw.lower().strip()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", email):
        return None
    if any(email.endswith(ext) for ext in _EMAIL_SKIP_EXTENSIONS):
        return None
    if any(skip in email for skip in _EMAIL_SKIP_DOMAINS):
        return None
    return email


def _clean_phone(raw: str, default_region: Optional[str] = None) -> Optional[str]:
    """Return a normalized E.164 phone string, or None if too short to be valid."""
    digits = re.sub(r"\D", "", raw)
    if len(digits) < 7:
        return None
    # Attempt E.164 normalization
    normalized = _normalize_phone(raw, default_region=default_region or "DE")
    if normalized:
        return normalized
    # Fallback: return raw stripped string
    return raw.strip()


def _dedupe(lst: List[str]) -> List[str]:
    """Deduplicate a list preserving order."""
    seen = set()
    out = []
    for item in lst:
        key = item.lower().strip()
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


def _extract_emails_from_html(html: str) -> List[str]:
    """Extract and clean email addresses from HTML."""
    soup = BeautifulSoup(html, "html.parser")
    emails: List[str] = []

    # 1. mailto: links (highest reliability)
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("mailto:"):
            addr = href[7:].split("?")[0].strip()
            cleaned = _clean_email(addr)
            if cleaned:
                emails.append(cleaned)

    # 2. Regex fallback on full HTML text
    for match in _EMAIL_RE.finditer(html):
        cleaned = _clean_email(match.group(0))
        if cleaned and cleaned not in emails:
            emails.append(cleaned)

    return _dedupe(emails)


def _extract_phones_from_html(html: str, default_region: Optional[str] = None) -> List[str]:
    """Extract phone numbers from HTML."""
    phones: List[str] = []

    # 1. tel: links
    for m in _TEL_RE.finditer(html):
        cleaned = _clean_phone(m.group(1), default_region=default_region)
        if cleaned:
            phones.append(cleaned)

    # 2. Text patterns
    for m in _PHONE_TEXT_RE.finditer(html):
        cleaned = _clean_phone(m.group(0), default_region=default_region)
        if cleaned and cleaned not in phones:
            phones.append(cleaned)

    return _dedupe(phones)


def _extract_whatsapp(html: str) -> List[str]:
    return _dedupe([m.group(0) for m in _WHATSAPP_RE.finditer(html)])


def _extract_messenger(html: str) -> List[str]:
    return _dedupe([m.group(0) for m in _MESSENGER_RE.finditer(html)])


def _extract_booking_links(html: str, base_url: str) -> List[str]:
    """Find booking platform links or internal reservation URLs."""
    soup = BeautifulSoup(html, "html.parser")
    links: List[str] = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        full = urljoin(base_url, href) if not href.startswith("http") else href
        parsed = urlparse(full)
        domain = parsed.netloc.lower().replace("www.", "")
        path_parts = set(parsed.path.lower().strip("/").split("/"))
        if domain in _BOOKING_DOMAINS or path_parts & _BOOKING_PATH_HINTS:
            if full not in links:
                links.append(full)
    return _dedupe(links)


def _extract_contact_form_urls(html: str, base_url: str) -> List[str]:
    """Find internal contact-page URLs."""
    soup = BeautifulSoup(html, "html.parser")
    urls: List[str] = []
    for a in soup.find_all("a", href=True):
        href = a["href"].lower()
        path = urlparse(href).path.strip("/")
        if any(hint in path for hint in _CONTACT_PATH_HINTS):
            full = urljoin(base_url, a["href"])
            if full not in urls:
                urls.append(full)
    return _dedupe(urls)


def _select_primary_contact_method(
    result: ContactResult,
    niche: str,
    instagram_reachable: bool = False,
    facebook_reachable: bool = False,
) -> Optional[str]:
    niche_lower = niche.lower()
    is_booking_heavy = any(kw in niche_lower for kw in _BOOKING_HEAVY_NICHES)

    if result.primary_email:
        return "email"
    if result.primary_phone:
        return "phone"
    if is_booking_heavy and result.booking_links:
        return "booking_link"
    if result.contact_form_urls:
        return "contact_form"
    if result.booking_links:
        return "booking_link"
    if result.whatsapp_links:
        return "whatsapp"
    if result.messenger_links:
        return "messenger"
    if instagram_reachable:
        return "instagram_dm"
    if facebook_reachable:
        return "facebook_message"
    return None


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class ContactDiscovery:
    """Extract, normalise, and deduplicate public contact data for a lead."""

    def __init__(self, timeout: int = 5) -> None:
        self._timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            )
        })

    def extract(
        self,
        lead: BusinessLead,
        website_response: Optional[requests.Response] = None,
    ) -> ContactResult:
        """Extract all public contacts for ``lead`` and return a ContactResult.

        Uses the cached ``website_response`` HTML if available.
        Makes at most ONE additional HTTP request (contact sub-page) when the
        main page yields no email.
        """
        result = ContactResult()
        base_url = lead.website_url or ""
        html = website_response.text if website_response is not None else ""

        # Derive ISO region code for phone normalization from lead country
        region = _COUNTRY_TO_REGION.get((lead.country or "").lower())

        # ── Extract from main page HTML ───────────────────────────────
        if html:
            result.all_emails = _extract_emails_from_html(html)
            result.all_phones = _extract_phones_from_html(html, default_region=region)
            result.whatsapp_links = _extract_whatsapp(html)
            result.messenger_links = _extract_messenger(html)
            result.booking_links = _extract_booking_links(html, base_url)
            result.contact_form_urls = _extract_contact_form_urls(html, base_url)

        # ── Second request: contact page (only if no email yet) ──────
        if not result.all_emails and result.contact_form_urls:
            contact_url = result.contact_form_urls[0]
            try:
                resp = self._session.get(contact_url, timeout=self._timeout)
                resp.raise_for_status()
                contact_html = resp.text
                extra_emails = _extract_emails_from_html(contact_html)
                result.all_emails = _dedupe(result.all_emails + extra_emails)
                # Also pick up phones/links from contact page
                extra_phones = _extract_phones_from_html(contact_html, default_region=region)
                result.all_phones = _dedupe(result.all_phones + extra_phones)
                extra_wa = _extract_whatsapp(contact_html)
                result.whatsapp_links = _dedupe(result.whatsapp_links + extra_wa)
                extra_bk = _extract_booking_links(contact_html, contact_url)
                result.booking_links = _dedupe(result.booking_links + extra_bk)
            except Exception as exc:
                log.debug("Contact sub-page fetch failed for %s: %s", contact_url, exc)

        # ── Merge existing lead data (Google Places phone is highest prio) ──
        if lead.phone and lead.phone not in result.all_phones:
            result.all_phones.insert(0, lead.phone)
        if lead.email and lead.email not in result.all_emails:
            result.all_emails.insert(0, lead.email)

        # Add existing whatsapp_url from social collector if present
        if lead.whatsapp_url and lead.whatsapp_url not in result.whatsapp_links:
            result.whatsapp_links.insert(0, lead.whatsapp_url)

        # ── Primary contact selection ─────────────────────────────────
        result.primary_email = result.all_emails[0] if result.all_emails else None
        result.primary_phone = result.all_phones[0] if result.all_phones else None

        # Instagram / Facebook reachability
        from ..enums import InstagramStatus
        ig_reachable = lead.instagram_status in (
            InstagramStatus.FOUND_ACTIVE, InstagramStatus.FOUND_ACTIVE_WITH_LINK
        )
        fb_reachable = bool(lead.facebook_url)

        result.primary_contact_method = _select_primary_contact_method(
            result,
            niche=lead.niche,
            instagram_reachable=ig_reachable,
            facebook_reachable=fb_reachable,
        )

        return result

    def apply_to_lead(
        self,
        lead: BusinessLead,
        result: ContactResult,
    ) -> None:
        """Write ContactResult fields back onto the BusinessLead.

        Does NOT overwrite existing non-null lead fields.
        """
        if not lead.primary_email and result.primary_email:
            lead.primary_email = result.primary_email
        lead.all_emails = _dedupe((lead.all_emails or []) + result.all_emails)

        if not lead.primary_phone and result.primary_phone:
            lead.primary_phone = result.primary_phone
        else:
            lead.primary_phone = lead.primary_phone or result.primary_phone
        lead.all_phones = _dedupe((lead.all_phones or []) + result.all_phones)

        lead.whatsapp_links = _dedupe((lead.whatsapp_links or []) + result.whatsapp_links)
        lead.messenger_links = _dedupe((lead.messenger_links or []) + result.messenger_links)
        lead.booking_links = _dedupe((lead.booking_links or []) + result.booking_links)
        lead.contact_form_urls = _dedupe((lead.contact_form_urls or []) + result.contact_form_urls)

        if not lead.primary_contact_method and result.primary_contact_method:
            lead.primary_contact_method = result.primary_contact_method
