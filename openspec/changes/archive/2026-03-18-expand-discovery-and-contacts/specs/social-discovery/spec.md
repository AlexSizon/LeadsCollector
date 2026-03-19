## MODIFIED Requirements

### Requirement: Discover Instagram business candidates for a niche × city query
The system SHALL, when `enable_social_discovery` is `true`, query publicly accessible Instagram pages to find business candidate profiles matching a given niche and city, and return a list of `SocialCandidate` objects. When a `SocialCandidate` with `source_platform="instagram"` is merged into a `BusinessLead`, the candidate's Instagram URL SHALL be stored in `lead.instagram_url` (not silently dropped).

#### Scenario: Discovery returns normalised candidates
- **WHEN** `InstagramDiscoveryCollector.search(niche="restaurant", city="Madrid", country="Spain")` is called
- **THEN** the collector SHALL return a list of `SocialCandidate` objects with at least `source_platform="instagram"`, `display_name`, `city`, and `niche` populated from the found profiles

#### Scenario: Instagram URL stored on merged lead
- **WHEN** `CrossSourceMatcher.merge_into(candidate, lead)` is called with a candidate whose `social_urls["instagram"]` is non-null
- **THEN** `lead.instagram_url` SHALL be set to that URL (if not already set)

#### Scenario: Instagram URL stored on stub lead created from unmatched candidate
- **WHEN** a `SocialCandidate` with `source_platform="instagram"` is promoted to a stub `BusinessLead`
- **THEN** `lead.instagram_url` SHALL be populated from `candidate.social_urls["instagram"]`

#### Scenario: Graceful empty result when platform is unreachable
- **WHEN** the underlying HTTP request to Instagram fails with a network error or 4xx/5xx response
- **THEN** the collector SHALL log a warning and return an empty list without raising an exception

#### Scenario: Respects configured request delay
- **WHEN** `social_request_delay` is set in config
- **THEN** the collector SHALL pause for at least that many seconds between HTTP requests to Instagram

### Requirement: Discover Facebook business candidates for a niche × city query
The system SHALL, when `enable_social_discovery` is `true`, query publicly accessible Facebook Pages search to find business candidate pages matching a given niche and city, and return a list of `SocialCandidate` objects. When a `SocialCandidate` with `source_platform="facebook"` is merged into a `BusinessLead`, the candidate's website URL and phone SHALL be stored on the lead if those fields were previously empty.

#### Scenario: Discovery returns normalised candidates
- **WHEN** `FacebookDiscoveryCollector.search(niche="beauty salon", city="Lisbon", country="Portugal")` is called
- **THEN** the collector SHALL return a list of `SocialCandidate` objects with at least `source_platform="facebook"`, `display_name`, `city`, and `niche` populated

#### Scenario: Graceful empty result when platform is unreachable
- **WHEN** any HTTP request fails with a network error or 4xx/5xx response
- **THEN** the collector SHALL log a warning and return an empty list without raising an exception

#### Scenario: Respects configured request delay
- **WHEN** `social_request_delay` is set in config
- **THEN** the collector SHALL pause for at least that many seconds between HTTP requests to Facebook
