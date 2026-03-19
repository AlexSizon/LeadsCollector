## ADDED Requirements

### Requirement: Compute business_strength_score
The system SHALL produce a normalised `business_strength_score` in [0, 100] based on Google reviews count, rating, niche value, and city attractiveness.

#### Scenario: High reviews and high rating produce high score
- **WHEN** a business has `google_reviews_count >= 100` and `google_rating >= 4.5`
- **THEN** `business_strength_score` SHALL be in the range [75, 100]

#### Scenario: Low reviews produce low base score
- **WHEN** a business has `google_reviews_count < 10`
- **THEN** `business_strength_score` SHALL not exceed 40

#### Scenario: Missing rating or reviews defaults to low score
- **WHEN** either `google_rating` or `google_reviews_count` is null
- **THEN** `business_strength_score` SHALL be set to 20

### Requirement: Compute website_problem_score
The system SHALL produce a normalised `website_problem_score` in [0, 100] where higher values indicate more severe website deficiencies.

#### Scenario: No website yields maximum problem score
- **WHEN** `website_status` is `NO_WEBSITE`
- **THEN** `website_problem_score` SHALL be in the range [85, 100]

#### Scenario: Broken website yields high problem score
- **WHEN** `website_status` is `BROKEN_WEBSITE`
- **THEN** `website_problem_score` SHALL be in the range [75, 95]

#### Scenario: Working website with multiple issues yields proportional score
- **WHEN** `website_status` is `HAS_WEBSITE` and `issues_found` contains 4 or more items
- **THEN** `website_problem_score` SHALL be in the range [50, 80]

#### Scenario: Working website with no issues yields low problem score
- **WHEN** `website_status` is `HAS_WEBSITE` and `issues_found` is empty
- **THEN** `website_problem_score` SHALL be in the range [0, 20]

### Requirement: Compute commercial_opportunity_score
The system SHALL produce a normalised `commercial_opportunity_score` in [0, 100] reflecting how commercially valuable a website improvement would be for this business.

#### Scenario: Niche with high local demand dependency scores higher
- **WHEN** the business niche is in the high-demand-dependency list (dentist, beauty salon, barbershop)
- **THEN** `commercial_opportunity_score` SHALL receive a niche-bonus of at least 15 points

#### Scenario: Active Instagram but no website amplifies opportunity score
- **WHEN** `instagram_status` is `FOUND_ACTIVE` or `FOUND_ACTIVE_WITH_LINK` AND `website_status` is `NO_WEBSITE` or `BROKEN_WEBSITE`
- **THEN** `commercial_opportunity_score` SHALL receive an additional bonus of at least 20 points

### Requirement: Compute lead_priority_score using weighted formula
The system SHALL combine the four sub-scores into a final `lead_priority_score` using a fixed weighting formula.

#### Scenario: Priority score uses defined weights
- **WHEN** all four sub-scores are computed
- **THEN** `lead_priority_score` SHALL equal `round(0.30 × business_strength_score + 0.35 × website_problem_score + 0.25 × commercial_opportunity_score + 0.10 × instagram_signal_score, 1)`

### Requirement: Assign lead tier based on priority score and key signals
The system SHALL assign each lead to a tier (1–4) for quick prioritisation.

#### Scenario: Tier 1 — strong business, no or broken website
- **WHEN** `business_strength_score >= 65` AND `website_status` is `NO_WEBSITE` or `BROKEN_WEBSITE`
- **THEN** the lead SHALL be classified as `Tier 1`

#### Scenario: Tier 4 — insufficient data or low activity
- **WHEN** `lead_priority_score < 30` OR `google_reviews_count < 10`
- **THEN** the lead SHALL be classified as `Tier 4`
