## ADDED Requirements

### Requirement: System records contact provenance for outreach decisions
The system SHALL record contact provenance for each outreach-usable channel. Provenance SHALL distinguish at minimum `scraped`, `json_ld`, `social`, `guessed`, and `manual`.

Eligibility and review decisions SHALL reference provenance rather than relying only on channel presence.

#### Scenario: Scraped email provenance recorded
- **WHEN** a lead email originates from website scraping or structured metadata extraction
- **THEN** the system SHALL record that provenance on the lead or outreach eligibility record

#### Scenario: Guessed email provenance recorded
- **WHEN** the only email contact for a lead comes from the MX-verified guesser
- **THEN** the system SHALL record `guessed` provenance and expose it to policy gating

### Requirement: System enforces suppression and objection handling
The system SHALL maintain a suppression list for contacts that must not receive future outreach. A suppressed contact SHALL be excluded from all future campaign eligibility checks.

Suppression SHALL support at minimum:
- explicit opt-out / objection
- manual operator suppression
- bounced address suppression

#### Scenario: Objection blocks future outreach
- **WHEN** a contact is marked as objected or opted out
- **THEN** the system SHALL exclude that contact from future campaign drafts and sends

#### Scenario: Hard bounce suppresses address
- **WHEN** an email address is marked as a hard bounce
- **THEN** that address SHALL be added to suppression before future eligibility checks

#### Scenario: Manual suppression takes effect immediately
- **WHEN** an operator manually suppresses a lead contact
- **THEN** the lead SHALL become ineligible for future outbound use on that channel

### Requirement: System applies country and channel policy rules before outreach
The system SHALL evaluate outreach actions against configured country and channel policy rules before any draft is approved, exported, or sent.

The policy result SHALL be one of:
- `allowed`
- `review_required`
- `blocked`

The result SHALL include a human-readable reason and policy version identifier.

#### Scenario: Blocked policy prevents approval
- **WHEN** the applicable country/channel policy result is `blocked`
- **THEN** the lead SHALL NOT be approvable for outbound email

#### Scenario: Review-required policy is visible to operator
- **WHEN** the applicable policy result is `review_required`
- **THEN** the viewer SHALL display the review reason before approval can be attempted

#### Scenario: Policy version is stored with send decision
- **WHEN** an outreach draft is approved or sent
- **THEN** the system SHALL record which policy version was used for that decision

### Requirement: System distinguishes contactable from sendable
The system SHALL treat “contactable” and “sendable” as separate concepts. A lead may have contact data and still be blocked from outreach because of provenance, suppression, or policy rules.

#### Scenario: Reachable but not sendable
- **WHEN** a lead has a guessed email or blocked policy state
- **THEN** the system SHALL allow the lead to remain visible as contactable while marking it non-sendable

#### Scenario: Sendable subset derived from reachability plus compliance
- **WHEN** the outreach workspace lists sendable leads
- **THEN** it SHALL include only leads that pass both channel reachability and compliance gating
