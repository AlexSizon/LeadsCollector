## ADDED Requirements

### Requirement: Generate outreach_angle using evidence-based formula
The system SHALL produce an `outreach_angle` string for each lead by combining detected business strength signals with observed website/presence gaps.

#### Scenario: No website, strong reviews
- **WHEN** `website_status` is `NO_WEBSITE` AND `google_reviews_count >= 50`
- **THEN** `outreach_angle` SHALL follow the pattern: `"Strong review profile ([N] reviews) but no owned website presence."`

#### Scenario: Broken website with active Instagram
- **WHEN** `website_status` is `BROKEN_WEBSITE` AND `instagram_status` starts with `FOUND_ACTIVE`
- **THEN** `outreach_angle` SHALL reference both the broken site and the active social presence

#### Scenario: Working website with weak conversion signals
- **WHEN** `website_status` is `HAS_WEBSITE` AND issues include CTA or booking-related items
- **THEN** `outreach_angle` SHALL reference the specific conversion gap observed

#### Scenario: No unsupported claims in angle
- **WHEN** generating `outreach_angle` for any lead
- **THEN** the output SHALL NOT contain superlatives, subjective judgements, or invented facts not derived from collected data signals

### Requirement: Generate short_pitch within defined constraints
The system SHALL produce a `short_pitch` of 1–3 sentences that is factual, non-pressuring, and focused on a specific benefit.

#### Scenario: Pitch references concrete benefit relevant to the niche
- **WHEN** the niche is `dentist` and the primary gap is `NO_WEBSITE`
- **THEN** `short_pitch` SHALL mention appointment-booking or patient-facing benefit

#### Scenario: Pitch does not exceed 3 sentences
- **WHEN** any `short_pitch` is generated
- **THEN** the sentence count SHALL not exceed 3

#### Scenario: Pitch avoids pressure language
- **WHEN** any `short_pitch` is generated
- **THEN** the text SHALL NOT contain phrases like "losing money", "urgent", "immediately", "you must", or similar high-pressure language
