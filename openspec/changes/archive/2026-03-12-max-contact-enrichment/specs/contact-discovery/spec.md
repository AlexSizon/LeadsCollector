## ADDED Requirements

### Requirement: Run email guesser as post-extraction fallback
The system SHALL, when `enable_email_guesser` is `true`, invoke `EmailGuesser.guess()` for any lead that has a known website domain but no email in `all_emails` after contact discovery completes.

#### Scenario: Guesser runs after contact extraction produces no email
- **WHEN** `ContactDiscovery.extract()` completes with `all_emails=[]` AND `lead.website_url` is non-null AND `enable_email_guesser` is `true`
- **THEN** the pipeline SHALL call `EmailGuesser.guess(lead.website_url, lead.niche)` and, if a result is returned, set `lead.guessed_email` to that result

#### Scenario: Guesser skipped when email already found
- **WHEN** `all_emails` is non-empty after contact extraction
- **THEN** `EmailGuesser` SHALL NOT be called for that lead

## MODIFIED Requirements

### Requirement: Feature flag controls contact discovery activation
The system SHALL only run contact discovery when `enable_contact_discovery: true` is in the run configuration.

#### Scenario: Contact discovery enabled by default
- **WHEN** `enable_contact_discovery` is absent from config or explicitly `true`
- **THEN** full contact extraction SHALL run for all leads with a website response

#### Scenario: Contact discovery disabled via flag
- **WHEN** `enable_contact_discovery` is `false`
- **THEN** NO additional HTTP requests for contact pages SHALL be made and `ContactResult` fields SHALL retain any values already set by `SocialCollector`
