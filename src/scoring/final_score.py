"""
Combine the individual component scores into a final lead priority
score according to the formula:

```
lead_priority = 0.30 * business_strength
               + 0.30 * website_problem
               + 0.25 * commercial_opportunity
               + 0.05 * instagram_signal
               + 0.10 * contactability
```

The ``contactability`` parameter defaults to 0.0 for backward
compatibility with callers that have not yet been updated.
"""

from typing import Optional, Tuple


def compute_final_score(
    business_strength: float,
    website_problem: float,
    commercial_opportunity: float,
    instagram_signal: float,
    contactability: float = 0.0,
    weights: Optional[dict] = None,
) -> float:
    """Return the weighted lead priority score (0–100).

    Parameters
    ----------
    weights : dict, optional
        Override the default component weights. Recognised keys:
        ``business_strength``, ``website_problem``,
        ``commercial_opportunity``, ``instagram_signal``,
        ``contactability``. Missing keys fall back to defaults.
    """
    w_bs  = (weights or {}).get("business_strength",    0.30)
    w_wp  = (weights or {}).get("website_problem",      0.30)
    w_co  = (weights or {}).get("commercial_opportunity", 0.25)
    w_is  = (weights or {}).get("instagram_signal",     0.05)
    w_ct  = (weights or {}).get("contactability",       0.10)
    return round(
        w_bs * business_strength
        + w_wp * website_problem
        + w_co * commercial_opportunity
        + w_is * instagram_signal
        + w_ct * contactability,
        1,
    )


def assign_tier(
    lead_priority_score: float,
    business_strength_score: float,
    website_status_value: str,
) -> int:
    """Assign tier 1–4 based on score and key signals.

    Tier 1: Strong business + no/broken website (highest priority)
    Tier 2: Good lead priority score (>= 55)
    Tier 3: Moderate lead priority score (>= 35)
    Tier 4: Low priority
    """
    no_or_broken = website_status_value in ("NO_WEBSITE", "BROKEN_WEBSITE")
    if business_strength_score >= 65 and no_or_broken:
        return 1
    if lead_priority_score >= 55:
        return 2
    if lead_priority_score >= 35:
        return 3
    return 4