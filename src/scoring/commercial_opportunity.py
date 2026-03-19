"""
Compute the commercial opportunity score for a lead.

This score estimates the potential upside from improving the website
conversion path. A business with strong demand but no effective
booking or contact flow scores higher.
"""

from typing import Optional
from ..enums import WebsiteStatus, InstagramStatus

# Niches where local web presence directly drives bookings/appointments
_HIGH_DEMAND_NICHES = frozenset({
    "dentist",
    "beauty salon",
    "barbershop",
    "physiotherapy",
    "hotel",
})


def compute_commercial_opportunity(
    status: WebsiteStatus,
    niche: str,
    city_demand_weight: float = 1.0,
    instagram_status: Optional[InstagramStatus] = None,
) -> float:
    """Return a score (0–100) estimating commercial opportunity.

    Parameters
    ----------
    status : WebsiteStatus
        The website presence classification for the business.
    niche : str
        The business niche (used for demand-dependency bonus).
    city_demand_weight : float
        Multiplier from ``scoring_rules.json`` city_attractiveness table.
    instagram_status : Optional[InstagramStatus]
        Instagram classification, used to amplify gap signals.
    """
    base = 45.0

    # --- Niche bonus (high local demand dependency) ---
    if niche.lower() in _HIGH_DEMAND_NICHES:
        base += 15

    # --- Website status bonus ---
    no_or_broken = status in {WebsiteStatus.NO_WEBSITE, WebsiteStatus.BROKEN_WEBSITE}
    if no_or_broken:
        base += 25
    elif status == WebsiteStatus.SOCIAL_ONLY:
        base += 20
    elif status == WebsiteStatus.HAS_WEBSITE:
        base += 10

    # --- Active Instagram signal bonus ---
    instagram_active = instagram_status in {
        InstagramStatus.FOUND_ACTIVE,
        InstagramStatus.FOUND_ACTIVE_WITH_LINK,
    }
    if instagram_active:
        if no_or_broken:
            # Business is generating social demand but has no web destination
            base += 20
        else:
            # Site exists but Instagram shows the audience is already there
            base += 10

    return min(base * city_demand_weight, 100.0)