## ADDED Requirements

### Requirement: Probe common email patterns for a website domain and verify via MX record
The system SHALL, when `enable_email_guesser` is `true` and a lead has a known website domain but no discovered email, attempt a set of common email-address patterns and return any address whose domain has a valid MX record.

#### Scenario: MX record exists — guessed address stored
- **WHEN** `email_guesser.guess(website_url="https://labella.es", niche="restaurant")` is called AND the domain `labella.es` has a resolvable MX record
- **THEN** `EmailGuesser.guess()` SHALL return the first matching pattern (e.g. `"info@labella.es"`) as a string

#### Scenario: No MX record — no address returned
- **WHEN** the domain has no MX record (e.g. a subdomain used only as a landing page)
- **THEN** `EmailGuesser.guess()` SHALL return `None` and log a debug message

#### Scenario: Patterns probed in priority order
- **WHEN** multiple patterns are tested
- **THEN** the system SHALL probe in order: `info@`, `contact@`, `hola@`, `hello@`, `contacto@`, `reservas@`, `bonjour@`, `bookings@` — returning on the first MX-valid pattern

#### Scenario: DNS timeout handled gracefully
- **WHEN** the DNS resolver times out (e.g. no network access)
- **THEN** `EmailGuesser.guess()` SHALL return `None` without raising an exception

### Requirement: Store guessed email separately from discovered email
The system SHALL persist a guessed email in a dedicated `guessed_email` field on `BusinessLead`, distinct from `primary_email` (which is reserved for directly scraped addresses).

#### Scenario: Guessed email stored in dedicated field
- **WHEN** the email guesser produces a result
- **THEN** `BusinessLead.guessed_email` SHALL be set to the guessed address and `primary_email` SHALL remain `None` if no scraped email was found

#### Scenario: Guessed email does not overwrite scraped email
- **WHEN** the lead already has a non-null `primary_email`
- **THEN** `EmailGuesser` SHALL NOT run and `guessed_email` SHALL remain `None`

### Requirement: Feature flag controls email guesser activation
The system SHALL only run the email guesser when `enable_email_guesser: true` is in the run configuration.

#### Scenario: Guesser disabled by default guard
- **WHEN** `enable_email_guesser` is `false` or absent
- **THEN** no DNS queries SHALL be made and `guessed_email` SHALL remain `None` on all leads
