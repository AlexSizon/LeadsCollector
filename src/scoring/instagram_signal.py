"""
Compute a simple score for Instagram activity.

Signals from Instagram indicate business maturity and marketing
activity. Active accounts with external links (e.g. to booking pages)
receive higher scores.
"""

from ..enums import InstagramStatus


def compute_instagram_signal(status: InstagramStatus) -> float:
    """Assign a score (0–100) based on Instagram status."""
    mapping = {
        InstagramStatus.NOT_FOUND: 0,
        InstagramStatus.FOUND_INACTIVE: 20,
        InstagramStatus.FOUND_ACTIVE: 60,
        InstagramStatus.FOUND_ACTIVE_WITH_LINK: 80,
        InstagramStatus.UNKNOWN: 30,  # Neutral — signal not determinable
    }
    return float(mapping.get(status, 0))