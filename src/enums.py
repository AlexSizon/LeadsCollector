"""
Enumerations used throughout the lead discovery pipeline.

These enums mirror the specification in the task prompt and help
avoid typos when referring to website and Instagram status values.
"""

from enum import Enum


class WebsiteStatus(str, Enum):
    """Represent the discovered website state for a business."""

    NO_WEBSITE = "NO_WEBSITE"
    SOCIAL_ONLY = "SOCIAL_ONLY"
    BROKEN_WEBSITE = "BROKEN_WEBSITE"
    HAS_WEBSITE = "HAS_WEBSITE"
    UNKNOWN = "UNKNOWN"


class InstagramStatus(str, Enum):
    """Represent the Instagram activity signal for a business."""

    NOT_FOUND = "NOT_FOUND"
    FOUND_INACTIVE = "FOUND_INACTIVE"
    FOUND_ACTIVE = "FOUND_ACTIVE"
    FOUND_ACTIVE_WITH_LINK = "FOUND_ACTIVE_WITH_LINK"
    UNKNOWN = "UNKNOWN"


class LeadSourceType(str, Enum):
    """Origin channel(s) for a lead."""

    OSM = "osm"
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    MERGED = "merged"
    UNKNOWN = "unknown"


class MatchConfidence(str, Enum):
    """Confidence level returned by CrossSourceMatcher."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNMATCHED = "UNMATCHED"
    NA = "N/A"


class ContactType(str, Enum):
    """Type of a discovered contact channel."""

    EMAIL = "email"
    PHONE = "phone"
    WHATSAPP = "whatsapp"
    FORM = "form"
    BOOKING = "booking"
    MESSENGER = "messenger"
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    WEBSITE = "website"
    ADDRESS = "address"
    OTHER = "other"


class ContactCategory(str, Enum):
    """Functional category of a discovered contact."""

    GENERAL = "general"
    SUPPORT = "support"
    SALES = "sales"
    BOOKINGS = "bookings"
    OWNER = "owner"
    MARKETING = "marketing"
    UNKNOWN = "unknown"


class SocialPresenceStatus(str, Enum):
    """Provenance of a discovered social profile URL.

    Records HOW a social link was discovered, not whether the account is active.
    """

    FOUND_ON_WEBSITE = "FOUND_ON_WEBSITE"
    FOUND_IN_SCHEMA = "FOUND_IN_SCHEMA"
    FOUND_VIA_HUB = "FOUND_VIA_HUB"
    FOUND_VIA_SEARCH = "FOUND_VIA_SEARCH"
    NOT_FOUND = "NOT_FOUND"
    UNKNOWN = "UNKNOWN"