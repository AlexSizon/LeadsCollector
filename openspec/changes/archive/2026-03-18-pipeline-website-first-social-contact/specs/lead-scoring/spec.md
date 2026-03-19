## ADDED Requirements

### Requirement: Apply niche demand weight from niches.json to business_strength_score
The system SHALL read the `local_demand_weight` value for each niche from `config/niches.json` and pass it as the `niche_weight` argument to `compute_business_strength()`. This wires the already-implemented `niche_weight` parameter that currently receives a hardcoded default of `1.0` in all call sites.

#### Scenario: High demand niche receives elevated business strength score
- **WHEN** a lead's niche is `"dentist"` (with `local_demand_weight: 0.90` in niches.json) and the business has `google_rating=4.5` and `google_reviews_count=80`
- **THEN** `business_strength_score` SHALL be higher than it would be for the same business in a niche with `local_demand_weight: 0.65`

#### Scenario: Low demand niche receives reduced business strength score
- **WHEN** a lead's niche has `local_demand_weight: 0.65` in niches.json
- **THEN** `compute_business_strength()` SHALL be called with `niche_weight=0.65`, producing a proportionally lower score than `niche_weight=1.0`

#### Scenario: Unknown niche falls back to default weight of 1.0
- **WHEN** a lead's niche does not appear in niches.json's niche registry
- **THEN** `compute_business_strength()` SHALL be called with `niche_weight=1.0`

#### Scenario: Niche weight applied consistently for both Google Places and social-stub leads
- **WHEN** a social-stub lead has a `niche` value matching an entry in niches.json
- **THEN** `compute_business_strength()` SHALL use the corresponding `local_demand_weight` value for that lead too

### Requirement: scoring_rules.json is the authoritative source for composite formula weights
The system SHALL load `config/scoring_rules.json` at pipeline initialization and pass the `final_score_weights` section to `compute_final_score()` rather than relying on hardcoded weight values inside the function. `scoring_rules.json` SHALL include a `contactability` key in `final_score_weights`, aligned with the code's current formula weight of `0.10`. The weights for `website_problem` (0.30) and `instagram_signal` (0.05) in `scoring_rules.json` SHALL match the code's current values.

#### Scenario: scoring_rules.json contactability weight is read and applied
- **WHEN** `scoring_rules.json` contains `"final_score_weights": { ..., "contactability": 0.10 }`
- **THEN** `compute_final_score()` SHALL apply that weight to the `contactability_score` component

#### Scenario: scoring_rules.json weights override hardcoded defaults when provided
- **WHEN** the pipeline passes a `weights` dict loaded from `scoring_rules.json` to `compute_final_score()`
- **THEN** the formula SHALL use those weights rather than the function's internal defaults

#### Scenario: Missing weight key falls back to hardcoded default
- **WHEN** the loaded `scoring_rules.json` does not include a particular weight key (e.g., `contactability` is absent from an older config file)
- **THEN** `compute_final_score()` SHALL fall back to the hardcoded default weight for that key without raising an exception

#### Scenario: Score formula produces correct weighted sum
- **WHEN** `compute_final_score()` is called with weights `{business_strength: 0.30, website_problem: 0.30, commercial_opportunity: 0.25, instagram_signal: 0.05, contactability: 0.10}` and sub-scores `[80, 70, 60, 40, 50]`
- **THEN** `lead_priority_score` SHALL equal `round(0.30×80 + 0.30×70 + 0.25×60 + 0.05×40 + 0.10×50, 1)` = `68.0`
