"""
Unit tests for all scoring modules.

Covers:
  - compute_business_strength(): null defaults, low-reviews cap, high-rating path
  - compute_website_problem_score(): all WebsiteStatus values, issue bonus
  - compute_commercial_opportunity(): niche bonus, Instagram bonus,
    Instagram+no-website amplifier
  - compute_final_score(): weighted formula arithmetic
  - assign_tier(): all four tier conditions
"""

from __future__ import annotations

import pytest

from src.enums import InstagramStatus, WebsiteStatus
from src.scoring.business_strength import compute_business_strength
from src.scoring.commercial_opportunity import compute_commercial_opportunity
from src.scoring.final_score import assign_tier, compute_final_score
from src.scoring.website_problem import compute_website_problem_score


# ---------------------------------------------------------------------------
# business_strength
# ---------------------------------------------------------------------------

class TestBusinessStrength:
    def test_null_rating_returns_default_not_zero(self):
        score = compute_business_strength(None, 50)
        assert score == 20.0

    def test_null_reviews_returns_default_not_zero(self):
        score = compute_business_strength(4.5, None)
        assert score == 20.0

    def test_both_null_returns_default(self):
        score = compute_business_strength(None, None)
        assert score == 20.0

    def test_low_reviews_capped_at_40(self):
        """Fewer than 10 reviews → score capped at 40."""
        score = compute_business_strength(5.0, 5)
        assert score <= 40.0

    def test_high_rating_high_reviews_above_40(self):
        score = compute_business_strength(4.8, 150)
        assert score > 40.0

    def test_perfect_rating_max_reviews_near_100(self):
        score = compute_business_strength(5.0, 200)
        assert score >= 90.0

    def test_zero_rating_zero_reviews_above_zero(self):
        """Even 0/0 inputs with niche_weight=1.0 should not go negative."""
        score = compute_business_strength(0.0, 0)
        assert score >= 0.0

    def test_niche_weight_multiplies_score(self):
        base = compute_business_strength(4.0, 50, niche_weight=1.0)
        boosted = compute_business_strength(4.0, 50, niche_weight=1.2)
        assert boosted > base

    def test_score_capped_at_100(self):
        score = compute_business_strength(5.0, 1000, niche_weight=10.0)
        assert score <= 100.0

    def test_score_between_0_and_100(self):
        for rating in [0.0, 2.5, 4.2, 5.0]:
            for reviews in [0, 5, 20, 100]:
                s = compute_business_strength(rating, reviews)
                assert 0.0 <= s <= 100.0, f"Out of range for rating={rating}, reviews={reviews}"


# ---------------------------------------------------------------------------
# website_problem_score
# ---------------------------------------------------------------------------

class TestWebsiteProblemScore:
    def test_no_website_base_85(self):
        score = compute_website_problem_score(WebsiteStatus.NO_WEBSITE, [])
        assert score == 85.0

    def test_broken_website_base_80(self):
        score = compute_website_problem_score(WebsiteStatus.BROKEN_WEBSITE, [])
        assert score == 80.0

    def test_social_only_base_70(self):
        score = compute_website_problem_score(WebsiteStatus.SOCIAL_ONLY, [])
        assert score == 70.0

    def test_has_website_base_40(self):
        score = compute_website_problem_score(WebsiteStatus.HAS_WEBSITE, [])
        assert score == 40.0

    def test_unknown_base_50(self):
        score = compute_website_problem_score(WebsiteStatus.UNKNOWN, [])
        assert score == 50.0

    def test_issue_bonus_adds_3_per_issue(self):
        score_no_issues = compute_website_problem_score(WebsiteStatus.HAS_WEBSITE, [])
        score_one_issue = compute_website_problem_score(WebsiteStatus.HAS_WEBSITE, ["Missing H1"])
        assert score_one_issue == score_no_issues + 3.0

    def test_issue_bonus_capped_at_15(self):
        many_issues = [f"Issue {i}" for i in range(20)]
        score = compute_website_problem_score(WebsiteStatus.HAS_WEBSITE, many_issues)
        assert score == 40.0 + 15.0

    def test_score_capped_at_100(self):
        many_issues = [f"Issue {i}" for i in range(20)]
        score = compute_website_problem_score(WebsiteStatus.NO_WEBSITE, many_issues)
        assert score <= 100.0


# ---------------------------------------------------------------------------
# commercial_opportunity
# ---------------------------------------------------------------------------

class TestCommercialOpportunity:
    def test_base_no_bonus(self):
        """Generic niche + has website + no Instagram = base 45 + 10 = 55."""
        score = compute_commercial_opportunity(
            WebsiteStatus.HAS_WEBSITE, "restaurant",
            city_demand_weight=1.0, instagram_status=None,
        )
        assert score == 55.0

    def test_high_demand_niche_bonus_15(self):
        score_dentist = compute_commercial_opportunity(
            WebsiteStatus.HAS_WEBSITE, "dentist", city_demand_weight=1.0,
        )
        score_generic = compute_commercial_opportunity(
            WebsiteStatus.HAS_WEBSITE, "restaurant", city_demand_weight=1.0,
        )
        assert score_dentist - score_generic == 15.0

    def test_no_website_bonus(self):
        score_no = compute_commercial_opportunity(
            WebsiteStatus.NO_WEBSITE, "restaurant", city_demand_weight=1.0,
        )
        score_has = compute_commercial_opportunity(
            WebsiteStatus.HAS_WEBSITE, "restaurant", city_demand_weight=1.0,
        )
        assert score_no > score_has

    def test_instagram_active_no_website_amplifier(self):
        """Active Instagram + no website should add extra bonus."""
        score_with_ig = compute_commercial_opportunity(
            WebsiteStatus.NO_WEBSITE, "restaurant", city_demand_weight=1.0,
            instagram_status=InstagramStatus.FOUND_ACTIVE,
        )
        score_no_ig = compute_commercial_opportunity(
            WebsiteStatus.NO_WEBSITE, "restaurant", city_demand_weight=1.0,
            instagram_status=None,
        )
        assert score_with_ig > score_no_ig

    def test_city_demand_weight_multiplies(self):
        score_1x = compute_commercial_opportunity(
            WebsiteStatus.NO_WEBSITE, "dentist", city_demand_weight=1.0,
        )
        score_1_1x = compute_commercial_opportunity(
            WebsiteStatus.NO_WEBSITE, "dentist", city_demand_weight=1.1,
        )
        assert score_1_1x > score_1x

    def test_score_capped_at_100(self):
        score = compute_commercial_opportunity(
            WebsiteStatus.NO_WEBSITE, "dentist",
            city_demand_weight=2.0,
            instagram_status=InstagramStatus.FOUND_ACTIVE_WITH_LINK,
        )
        assert score <= 100.0

    def test_beauty_salon_is_high_demand(self):
        score = compute_commercial_opportunity(
            WebsiteStatus.HAS_WEBSITE, "beauty salon", city_demand_weight=1.0,
        )
        assert score == 45.0 + 15.0 + 10.0  # base + niche + has_website


# ---------------------------------------------------------------------------
# final_score & tier
# ---------------------------------------------------------------------------

class TestFinalScore:
    def test_weighted_formula(self):
        # Formula: 0.30*BS + 0.30*WP + 0.25*CO + 0.05*IG + 0.10*CA (contactability defaults 0.0)
        score = compute_final_score(80, 70, 60, 50)
        expected = round(0.30 * 80 + 0.30 * 70 + 0.25 * 60 + 0.05 * 50 + 0.10 * 0.0, 1)
        assert score == expected

    def test_weighted_formula_with_contactability(self):
        score = compute_final_score(80, 70, 60, 50, contactability=40)
        expected = round(0.30 * 80 + 0.30 * 70 + 0.25 * 60 + 0.05 * 50 + 0.10 * 40, 1)
        assert score == expected

    def test_all_zero_returns_zero(self):
        assert compute_final_score(0, 0, 0, 0) == 0.0

    def test_all_100_returns_100(self):
        assert compute_final_score(100, 100, 100, 100, contactability=100) == 100.0

    def test_result_rounded_to_1dp(self):
        score = compute_final_score(33.33, 66.66, 50.0, 25.0)
        assert score == round(score, 1)


class TestAssignTier:
    def test_tier_1_strong_business_no_website(self):
        tier = assign_tier(
            lead_priority_score=70,
            business_strength_score=70,
            website_status_value="NO_WEBSITE",
        )
        assert tier == 1

    def test_tier_1_broken_website(self):
        tier = assign_tier(
            lead_priority_score=40,
            business_strength_score=80,
            website_status_value="BROKEN_WEBSITE",
        )
        assert tier == 1

    def test_tier_2_good_priority_score(self):
        tier = assign_tier(
            lead_priority_score=58,
            business_strength_score=40,
            website_status_value="HAS_WEBSITE",
        )
        assert tier == 2

    def test_tier_3_moderate_score(self):
        tier = assign_tier(
            lead_priority_score=45,
            business_strength_score=30,
            website_status_value="HAS_WEBSITE",
        )
        assert tier == 3

    def test_tier_4_low_everything(self):
        tier = assign_tier(
            lead_priority_score=20,
            business_strength_score=30,
            website_status_value="HAS_WEBSITE",
        )
        assert tier == 4

    def test_tier_1_requires_strength_threshold(self):
        """Strength < 65 should not qualify for Tier 1."""
        tier = assign_tier(
            lead_priority_score=80,
            business_strength_score=60,
            website_status_value="NO_WEBSITE",
        )
        # Not tier 1 (strength too low), but priority 80 → tier 2
        assert tier == 2

    def test_has_website_with_high_strength_not_tier1(self):
        """Tier 1 requires no/broken website, not just high strength."""
        tier = assign_tier(
            lead_priority_score=30,
            business_strength_score=90,
            website_status_value="HAS_WEBSITE",
        )
        assert tier != 1
