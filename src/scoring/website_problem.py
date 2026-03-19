"""
Compute the website problem score based on the website status and audit findings.

Higher scores indicate more severe problems and therefore larger
commercial opportunity for improvement.
"""

from typing import List
from ..enums import WebsiteStatus

_BASE_SCORES = {
    WebsiteStatus.NO_WEBSITE: 85,
    WebsiteStatus.SOCIAL_ONLY: 70,
    WebsiteStatus.BROKEN_WEBSITE: 80,
    WebsiteStatus.HAS_WEBSITE: 40,
    WebsiteStatus.UNKNOWN: 50,
}

_ISSUE_POINTS_EACH = 3
_ISSUE_BONUS_CAP = 15


def compute_website_problem_score(status: WebsiteStatus, issues: List[str]) -> float:
    """Calculate a score (0–100) representing the severity of website problems.

    Parameters
    ----------
    status : WebsiteStatus
        The classified website presence state.
    issues : List[str]
        Issues discovered by the audit stage.
    """
    base = float(_BASE_SCORES.get(status, 50))
    # Bonus for each identified issue (capped to avoid over-weighting)
    bonus = min(len(issues) * _ISSUE_POINTS_EACH, _ISSUE_BONUS_CAP)
    return min(base + bonus, 100.0)