## ADDED Requirements

### Requirement: Discover hospitality business candidates via TripAdvisor
The system SHALL, when `enable_tripadvisor_discovery` is `true` and the current niche is in the hospitality set, query TripAdvisor via Google site-search and return a list of `SocialCandidate` objects with phone and website data.

#### Scenario: Discovery returns candidates for hospitality niche
- **WHEN** `TripAdvisorCollector.search(niche="restaurant", city="Lisbon", country="Portugal")` is called
- **THEN** the collector SHALL return a list of `SocialCandidate` objects with `source_platform="tripadvisor"`, `display_name`, `city`, `niche`, and any extractable `phone` or `website_url`

#### Scenario: Non-hospitality niche returns empty list immediately
- **WHEN** `TripAdvisorCollector.search(niche="florist", city="Madrid", ...)` is called
- **THEN** `TripAdvisorCollector` SHALL return `[]` immediately without making any HTTP requests (niche guard)

#### Scenario: Graceful empty result on network error
- **WHEN** any HTTP request fails
- **THEN** the collector SHALL return `[]` and log a warning; the pipeline SHALL continue unaffected

#### Scenario: Respects configured request delay
- **WHEN** `social_request_delay` is set in config
- **THEN** the collector SHALL pause at least that many seconds between requests

### Requirement: Extract phone number from TripAdvisor public listing page
The system SHALL, when fetching a TripAdvisor listing page, attempt to extract any visible phone number from the page HTML.

#### Scenario: Phone extracted from TripAdvisor page
- **WHEN** a TripAdvisor listing page contains a visible phone number in its HTML
- **THEN** the returned `SocialCandidate.phone` SHALL contain that phone number

#### Scenario: No phone on page — field remains None
- **WHEN** no phone pattern is found on the TripAdvisor page HTML
- **THEN** `SocialCandidate.phone` SHALL be `None`

### Requirement: TripAdvisor collector obeys hospitality-niche scope
The hospitality niche set is: `restaurant`, `café`, `café-bar`, `bar`, `bakery`.
The system SHALL NOT run TripAdvisor discovery for any niche outside this set.

#### Scenario: Scope enforced at search time
- **WHEN** a niche not in the hospitality set is passed to `TripAdvisorCollector.search()`
- **THEN** the method SHALL return `[]` without any HTTP requests
