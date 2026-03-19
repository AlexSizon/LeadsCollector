## ADDED Requirements

### Requirement: System classifies leads for email-first outreach eligibility
The system SHALL classify each lead into email outreach eligibility states before campaign draft creation. Eligibility SHALL distinguish at minimum `allowed`, `review_required`, and `blocked`, and SHALL store the reason for the decision.

Direct business emails scraped from public business websites or structured business metadata SHALL be eligible by default unless blocked by suppression or policy rules. Guessed-only email addresses SHALL NOT be eligible by default.

#### Scenario: Scraped business email is allowed
- **WHEN** a lead has a public business email from scraped or structured website sources AND no suppression or policy block applies
- **THEN** the lead SHALL be marked `email_eligibility=allowed` with a reason indicating the accepted provenance

#### Scenario: Guessed-only email is blocked by default
- **WHEN** a lead has no direct email and only `guessed_email` is present
- **THEN** the lead SHALL be marked `email_eligibility=blocked` unless an explicit manual override policy is enabled

#### Scenario: Policy ambiguity requires review
- **WHEN** a lead has an email channel that is not clearly blocked but requires manual legal or operator review under the configured policy
- **THEN** the lead SHALL be marked `email_eligibility=review_required` with a human-readable reason

### Requirement: System generates outreach drafts for website offer types
The system SHALL generate outreach drafts for eligible leads using one of two offer types: `new-website` or `website-improvement`. Each draft SHALL include rendered email subject, opening, body preview, CTA, and the evidence fields used to support the message.

The default offer type SHALL derive from lead evidence:
- `new-website` for `NO_WEBSITE` or `SOCIAL_ONLY`
- `website-improvement` for `HAS_WEBSITE` or `BROKEN_WEBSITE`

#### Scenario: New-website draft from missing website
- **WHEN** a lead has `website_status=NO_WEBSITE`
- **THEN** the generated outreach draft SHALL default to `offer_type=new-website`

#### Scenario: Website-improvement draft from weak or broken site
- **WHEN** a lead has `website_status=HAS_WEBSITE` or `website_status=BROKEN_WEBSITE`
- **THEN** the generated outreach draft SHALL default to `offer_type=website-improvement`

#### Scenario: Draft stores supporting evidence
- **WHEN** an outreach draft is created
- **THEN** it SHALL store the evidence snapshot used for the message, including relevant website status, issues, and outreach angle inputs

### Requirement: Human approval is required before a draft becomes sendable
The system SHALL require explicit human approval before an outreach draft can be included in a sendable or exportable campaign batch.

Approval SHALL store the approver identity, approval timestamp, final offer type, and final rendered message snapshot.

#### Scenario: Unapproved draft cannot be sent
- **WHEN** a draft has not been approved
- **THEN** the system SHALL block send and export actions that target it as an outbound campaign item

#### Scenario: Approved draft becomes sendable
- **WHEN** an operator approves an outreach draft
- **THEN** the draft SHALL move into an approved state with the approval metadata recorded

### Requirement: System supports dry-run, export-only, and direct-send execution modes
The system SHALL support three execution modes for email-first campaigns:
- `dry-run`
- `export-only`
- `direct-send`

`direct-send` SHALL only be available when sender configuration preflight succeeds.

#### Scenario: Dry-run renders without delivery
- **WHEN** a campaign is executed in `dry-run` mode
- **THEN** the system SHALL render the final messages and campaign summary without transmitting any emails

#### Scenario: Export-only produces batch payloads
- **WHEN** a campaign is executed in `export-only` mode
- **THEN** the system SHALL create export artifacts containing the approved outreach messages and recipient metadata without transmitting any emails

#### Scenario: Direct-send requires successful preflight
- **WHEN** a campaign is executed in `direct-send` mode
- **THEN** the system SHALL verify sender configuration and block the send if preflight has not succeeded
