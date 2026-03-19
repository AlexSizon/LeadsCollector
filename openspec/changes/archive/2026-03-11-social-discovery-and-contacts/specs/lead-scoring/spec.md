## ADDED Requirements

### Requirement: Compute contactability_score
The system SHALL produce a normalised `contactability_score` in [0, 100] reflecting the breadth and quality of available contact channels for a business.

#### Scenario: Email present yields highest channel contribution
- **WHEN** a business has a confirmed email in `all_emails`
- **THEN** `contactability_score` SHALL include at least 30 points from the email channel

#### Scenario: Multiple channels produce additive score
- **WHEN** a business has email, phone, and a booking link
- **THEN** `contactability_score` SHALL be higher than a business with only one channel, up to a maximum of 100

#### Scenario: No contact channels yields score of zero
- **WHEN** all contact fields (`email`, `phone`, `whatsapp_links`, `booking_links`, `contact_form_urls`) are empty or null
- **THEN** `contactability_score` SHALL be `0`

#### Scenario: Social-first lead with reachable DM scores above zero
- **WHEN** a social-first lead has no email or phone but has a non-null `instagram_status` of `FOUND_ACTIVE`
- **THEN** `contactability_score` SHALL be greater than 0 to reflect the Instagram DM channel

### Requirement: Include contactability_score in lead_priority_score formula
The system SHALL update the `lead_priority_score` formula to incorporate `contactability_score`.

#### Scenario: Updated priority formula
- **WHEN** all five sub-scores are computed
- **THEN** `lead_priority_score` SHALL equal `round(0.30 × business_strength_score + 0.30 × website_problem_score + 0.25 × commercial_opportunity_score + 0.05 × instagram_signal_score + 0.10 × contactability_score, 1)`

### Requirement: Record match_confidence on each BusinessLead
The system SHALL store the `CrossSourceMatcher` confidence level on each `BusinessLead` for export and observability.

#### Scenario: OSM-only lead has no match confidence
- **WHEN** a lead is sourced exclusively from OSM with no social candidate match attempted
- **THEN** `match_confidence` SHALL be `"N/A"` or an empty string

#### Scenario: Social-matched lead records confidence level
- **WHEN** a social candidate matches an existing lead with `HIGH` confidence
- **THEN** `match_confidence` SHALL be `"HIGH"` on the resulting lead

#### Scenario: Social-first unmatched lead records UNMATCHED
- **WHEN** a social candidate has no match
- **THEN** `match_confidence` SHALL be `"UNMATCHED"` on the new lead
