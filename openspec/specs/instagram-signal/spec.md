## ADDED Requirements

### Requirement: Locate Instagram handle for a business
The system SHALL attempt to find an Instagram handle for each business using available signals (website link extraction, business name search heuristics).

#### Scenario: Instagram handle found in website HTML
- **WHEN** the business website HTML contains a link to `instagram.com/<handle>`
- **THEN** the system SHALL extract and store the handle

#### Scenario: Instagram handle not locatable
- **WHEN** no Instagram handle can be found via website HTML or place metadata
- **THEN** `instagram_status` SHALL be `UNKNOWN` (NOT `NOT_FOUND`)

### Requirement: Classify Instagram presence using public profile signals
The system SHALL fetch the public Instagram profile page (unauthenticated) for any discovered handle and classify it using a typed enum.

#### Scenario: Profile page not reachable or returns 404
- **WHEN** the HTTP request to `https://www.instagram.com/<handle>/` returns 404 or a connection error
- **THEN** `instagram_status` SHALL be `NOT_FOUND`

#### Scenario: Profile exists but shows low activity signals
- **WHEN** the profile page is reachable but post-count signals indicate fewer than 10 posts and no recent activity metadata
- **THEN** `instagram_status` SHALL be `FOUND_INACTIVE`

#### Scenario: Profile exists with active posting signals
- **WHEN** the profile page is reachable and post-count signals indicate 10 or more posts
- **THEN** `instagram_status` SHALL be at minimum `FOUND_ACTIVE`

#### Scenario: Active profile has a link in bio
- **WHEN** `instagram_status` would be `FOUND_ACTIVE` and the profile page contains a detectable external link in the bio
- **THEN** `instagram_status` SHALL be upgraded to `FOUND_ACTIVE_WITH_LINK`

### Requirement: Compute instagram_signal_score
The system SHALL produce a numeric `instagram_signal_score` in [0, 100] based on the classified Instagram status and detected signals.

#### Scenario: Score reflects status tier
- **WHEN** `instagram_status` is `FOUND_ACTIVE_WITH_LINK`
- **THEN** `instagram_signal_score` SHALL be in the range [65, 100]

#### Scenario: Not found yields low score
- **WHEN** `instagram_status` is `NOT_FOUND`
- **THEN** `instagram_signal_score` SHALL be in the range [0, 20]

#### Scenario: Unknown yields neutral mid-range score
- **WHEN** `instagram_status` is `UNKNOWN`
- **THEN** `instagram_signal_score` SHALL be set to 30
