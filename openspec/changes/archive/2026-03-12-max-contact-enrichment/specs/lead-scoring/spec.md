## ADDED Requirements

### Requirement: Award partial contactability points for MX-verified guessed email
The system SHALL award a reduced contactability bonus for a `guessed_email` (MX-verified domain pattern) compared to a directly scraped `primary_email`.

#### Scenario: Guessed email contributes to contactability score
- **WHEN** `lead.guessed_email` is non-null AND `lead.primary_email` is null
- **THEN** `contactability_score` SHALL include 15 points for the guessed email channel (vs 30 points for a scraped email)

#### Scenario: Guessed email does not stack with scraped email
- **WHEN** `lead.primary_email` is non-null (scraped email present)
- **THEN** the 30-point scraped email bonus applies and the guessed email bonus SHALL NOT be added additionally

#### Scenario: Lead with guessed email only reaches minimum contactability
- **WHEN** a lead has `guessed_email` set and no other contact channels
- **THEN** `contactability_score` SHALL equal 15
