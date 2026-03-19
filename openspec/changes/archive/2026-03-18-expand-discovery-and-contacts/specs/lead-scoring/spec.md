## MODIFIED Requirements

### Requirement: Compute contactability_score in all pipeline entry points
The system SHALL compute `contactability_score` for every `BusinessLead` produced by any pipeline entry point (both `LeadPipeline` in `src/pipeline.py` and `run_europe_smb.py`). The score SHALL NOT remain `0.0` by default when contact discovery is enabled.

#### Scenario: contactability_score computed when contact discovery is enabled
- **WHEN** `enable_contact_discovery` is `true` and a lead has been through `ContactDiscovery`
- **THEN** `compute_contactability_score(lead)` SHALL be called and the result SHALL be stored in `lead.contactability_score`

#### Scenario: contactability_score passed to compute_final_score
- **WHEN** `compute_final_score()` is called for a lead
- **THEN** the `contactability` argument SHALL be the computed `contactability_score` value, not a hardcoded `0.0`

#### Scenario: contactability_score defaults to 0.0 when contact discovery is disabled
- **WHEN** `enable_contact_discovery` is `false`
- **THEN** `contactability_score` MAY remain `0.0` and `compute_final_score()` SHALL still be called with `contactability=0.0`

#### Scenario: contactability_score appears in all output formats
- **WHEN** any lead is exported
- **THEN** `contactability_score` SHALL appear in both JSON and CSV output

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

#### Scenario: No website produces highest score
- **WHEN** `website_status` is `NO_WEBSITE`
- **THEN** `website_problem_score` SHALL be in the range [80, 100]

#### Scenario: Broken website produces high score
- **WHEN** `website_status` is `BROKEN_WEBSITE`
- **THEN** `website_problem_score` SHALL be in the range [75, 95]

#### Scenario: Working website produces low base score
- **WHEN** `website_status` is `HAS_WEBSITE` and no audit issues are found
- **THEN** `website_problem_score` SHALL be at most 45
