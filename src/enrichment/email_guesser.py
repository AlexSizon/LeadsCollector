"""
Email address guesser using MX record verification.

Strategy:
1. Extract the root domain from the business website URL.
2. Verify the domain can receive email by checking for MX records
   via ``dns.resolver`` — no email is ever sent.
3. Return the first pattern-based address that is likely for the
   business niche (e.g. ``info@example.com``).

Design decision D2: purely passive — we only check that the domain
*has* MX records, never probe individual mailboxes or send messages.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

log = logging.getLogger(__name__)

# Ordered probe patterns — most generic first, then locale-specific
_DEFAULT_PATTERNS = [
    "info",
    "contact",
    "hola",
    "hello",
    "contacto",
    "reservas",
    "bonjour",
    "bookings",
]

# Niches that typically use reservation-centric addresses
_HOSPITALITY_NICHES = {"restaurant", "bakery", "café", "café-bar", "bar"}


class EmailGuesser:
    """Guess a likely contact email address for a business domain.

    Usage::

        guesser = EmailGuesser()
        email = guesser.guess("https://www.example.com", niche="restaurant")
        # "reservas@example.com" or None
    """

    def __init__(self) -> None:
        # Lazy import so the module is usable even if dnspython is not
        # installed — callers will simply get None from guess().
        try:
            import dns.resolver  # noqa: F401  (test import)
            self._dns_available = True
        except ImportError:
            log.warning("dnspython not installed — EmailGuesser will always return None")
            self._dns_available = False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_domain(website_url: str) -> Optional[str]:
        """Return the bare domain from *website_url*, stripping scheme/www/path/port.

        Examples::

            "https://www.example.com/path?q=1" → "example.com"
            "http://shop.example.co.uk:8080/"  → "shop.example.co.uk"
        """
        if not website_url:
            return None
        # Strip scheme
        url = re.sub(r"^https?://", "", website_url.strip(), flags=re.IGNORECASE)
        # Strip www. prefix
        url = re.sub(r"^www\.", "", url, flags=re.IGNORECASE)
        # Strip port
        url = re.sub(r":\d+", "", url)
        # Strip path, query, fragment — take only the host portion
        domain = url.split("/")[0].split("?")[0].split("#")[0].strip()
        return domain if domain else None

    def _check_mx(self, domain: str) -> bool:
        """Return True if *domain* has at least one MX record, False otherwise."""
        if not self._dns_available:
            return False
        try:
            import dns.resolver
            dns.resolver.resolve(domain, "MX")
            return True
        except Exception as exc:
            log.debug("MX lookup failed for %s: %s", domain, exc)
            return False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def guess(self, website_url: str, niche: Optional[str] = None) -> Optional[str]:
        """Return a guessed email address for *website_url*, or None.

        The address is purely pattern-based (``info@domain.com``) and is
        only returned after confirming the domain has MX records.

        Args:
            website_url: The business website URL to derive the domain from.
            niche: Optional business niche used to select the best prefix
                (e.g. "restaurant" → "reservas" first).

        Returns:
            A guessed email string such as ``"info@example.com"``, or
            ``None`` if the domain is unresolvable or has no MX records.
        """
        domain = self._extract_domain(website_url)
        if not domain:
            return None

        if not self._check_mx(domain):
            return None

        # Build ordered pattern list based on niche
        patterns = list(_DEFAULT_PATTERNS)
        if niche and niche.lower() in _HOSPITALITY_NICHES:
            # Hospitality businesses are more likely to use reservation prefixes
            for prefix in ("bookings", "reservas"):
                if prefix in patterns:
                    patterns.remove(prefix)
                patterns.insert(0, prefix)

        email = f"{patterns[0]}@{domain}"
        log.info("Guessed email for %s: %s (MX verified)", domain, email)
        return email
