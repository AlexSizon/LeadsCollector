"""
Compute the business strength score based on signals like Google ratings,
review counts, niche value and location attractiveness.
"""

from typing import Optional

_NULL_DEFAULT = 20.0          # Score when rating or reviews data is missing
_LOW_REVIEWS_THRESHOLD = 10  # Below this count the score is capped
_LOW_REVIEWS_CAP = 40.0      # Maximum score when reviews < threshold


def compute_business_strength(
    rating: Optional[float],
    reviews: Optional[int],
    niche_weight: float = 1.0,
) -> float:
    """Return a score between 0 and 100 representing the business's strength.

    The score rewards higher ratings and more reviews. Null inputs default
    to a conservative low score rather than zero to avoid penalising
    incomplete data too harshly.

    Parameters
    ----------
    rating : Optional[float]
        Google rating (0–5). None → default score.
    reviews : Optional[int]
        Google review count. None → default score.
    niche_weight : float
        Multiplier for niche commercial value (default 1.0 = neutral).
    """
    if rating is None or reviews is None:
        return _NULL_DEFAULT * niche_weight

    rating_score = (rating / 5.0) * 50       # Up to 50 points from rating
    review_score = min(reviews, 100) / 100 * 50  # Up to 50 points from reviews (saturates at 100)
    raw = (rating_score + review_score) * niche_weight

    # Cap when very few reviews — signal is unreliable
    if reviews < _LOW_REVIEWS_THRESHOLD:
        return min(raw, _LOW_REVIEWS_CAP)

    return min(raw, 100.0)