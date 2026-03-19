## ADDED Requirements

### Requirement: Generate email-specific outreach copy from lead evidence
The system SHALL generate email-specific outreach copy for outreach-ready leads in addition to the existing `outreach_angle` and `short_pitch` fields.

Generated email-specific fields SHALL include:
- `offer_type`
- `email_subject`
- `email_opening`
- `email_cta`
- `email_body_preview`

#### Scenario: Email subject generated for outreach-ready lead
- **WHEN** a lead is marked eligible for email outreach draft creation
- **THEN** the system SHALL generate an `email_subject` grounded in that lead's observed evidence

#### Scenario: Email opening references factual lead evidence
- **WHEN** the system generates `email_opening`
- **THEN** the opening SHALL reference only facts already derived from collected lead signals

### Requirement: Offer type derives from website situation with manual override support
The system SHALL assign one of two offer types to an outreach draft: `new-website` or `website-improvement`.

Default assignment SHALL be:
- `new-website` for `NO_WEBSITE` and `SOCIAL_ONLY`
- `website-improvement` for `HAS_WEBSITE` and `BROKEN_WEBSITE`

Operators SHALL be able to override the offer type during review before approval.

#### Scenario: New-website offer for no website
- **WHEN** `website_status=NO_WEBSITE`
- **THEN** the generated outreach draft SHALL default to `offer_type=new-website`

#### Scenario: Website-improvement offer for existing site
- **WHEN** `website_status=HAS_WEBSITE` or `website_status=BROKEN_WEBSITE`
- **THEN** the generated outreach draft SHALL default to `offer_type=website-improvement`

#### Scenario: Operator override changes offer type
- **WHEN** an operator overrides the default offer type during review
- **THEN** the final approved draft SHALL use the overridden offer type

### Requirement: Generated email copy remains factual and low-pressure
Email-specific outreach copy SHALL remain factual, non-pressuring, and evidence-based. It SHALL NOT introduce unsupported claims, fake urgency, or unverifiable performance promises.

#### Scenario: Subject avoids pressure language
- **WHEN** the system generates an email subject
- **THEN** the subject SHALL NOT contain coercive phrases such as "urgent", "you must", or equivalent pressure language

#### Scenario: CTA remains specific and bounded
- **WHEN** the system generates `email_cta`
- **THEN** the CTA SHALL request a bounded next step such as reply, quick review, or booking link click instead of making unverifiable claims
