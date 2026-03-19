## ADDED Requirements

### Requirement: Discover Instagram business candidates for a niche × city query
The system SHALL, when `enable_social_discovery` is `true`, query publicly accessible Instagram pages to find business candidate profiles matching a given niche and city, and return a list of `SocialCandidate` objects.

#### Scenario: Discovery returns normalised candidates
- **WHEN** `InstagramDiscoveryCollector.search(niche="restaurant", city="Madrid", country="Spain")` is called
- **THEN** the collector SHALL return a list of `SocialCandidate` objects with at least `source_platform="instagram"`, `display_name`, `city`, and `niche` populated from the found profiles

#### Scenario: Graceful empty result when platform is unreachable
- **WHEN** the underlying HTTP request to Instagram fails with a network error or 4xx/5xx response
- **THEN** the collector SHALL log a warning and return an empty list without raising an exception

#### Scenario: Respects configured request delay
- **WHEN** `social_request_delay` is set in config
- **THEN** the collector SHALL pause for at least that many seconds between HTTP requests to Instagram

### Requirement: Discover Facebook business candidates for a niche × city query
The system SHALL, when `enable_social_discovery` is `true`, query publicly accessible Facebook Pages search to find business candidate pages matching a given niche and city, and return a list of `SocialCandidate` objects.

#### Scenario: Discovery returns normalised candidates
- **WHEN** `FacebookDiscoveryCollector.search(niche="beauty salon", city="Amsterdam", country="Netherlands")` is called
- **THEN** the collector SHALL return a list of `SocialCandidate` objects with `source_platform="facebook"`, `display_name`, and at least one of: `phone`, `email`, `website_url`, `social_urls`

#### Scenario: Graceful empty result when platform is unreachable
- **WHEN** any HTTP request to Facebook fails
- **THEN** the collector SHALL return an empty list and log a warning; the pipeline SHALL continue unaffected

### Requirement: Represent a social-discovered candidate as a SocialCandidate
The system SHALL use a `SocialCandidate` model to hold lead data discovered from social platforms before cross-source matching.

#### Scenario: SocialCandidate carries all discoverable fields
- **WHEN** a profile is discovered on Instagram or Facebook
- **THEN** a `SocialCandidate` SHALL be created with fields: `source_platform`, `handle_or_page_id`, `display_name`, `city`, `country`, `niche`, `website_url`, `phone`, `email`, `social_urls (dict)`, `raw_bio`

#### Scenario: Missing optional fields default to None
- **WHEN** a discovered profile has no phone or website link
- **THEN** those fields in `SocialCandidate` SHALL be `None`, not absent

### Requirement: Cross-source matcher assigns confidence to candidate-lead pairs
The system SHALL match each `SocialCandidate` against existing `BusinessLead` objects using a multi-signal scoring algorithm and return a `MatchResult` with confidence level.

#### Scenario: HIGH confidence match on name + domain
- **WHEN** normalised name similarity ≥ 0.85 AND website domain matches an existing lead's domain
- **THEN** `CrossSourceMatcher` SHALL return `MatchResult(confidence="HIGH", matched_index=<idx>)`

#### Scenario: HIGH confidence match on name + phone
- **WHEN** normalised name similarity ≥ 0.85 AND phone (E.164 normalised) matches an existing lead
- **THEN** `CrossSourceMatcher` SHALL return `MatchResult(confidence="HIGH", matched_index=<idx>)`

#### Scenario: MEDIUM confidence match on name + city
- **WHEN** normalised name similarity ≥ 0.70 AND city matches but no phone/domain overlap
- **THEN** `CrossSourceMatcher` SHALL return `MatchResult(confidence="MEDIUM", matched_index=<idx>)`

#### Scenario: UNMATCHED candidate
- **WHEN** no existing lead meets the LOW confidence threshold (name similarity < 0.55)
- **THEN** `CrossSourceMatcher` SHALL return `MatchResult(confidence="UNMATCHED", matched_index=None)`

### Requirement: HIGH-confidence matches merge social data into existing lead
The system SHALL, for `HIGH` confidence matches, merge the `SocialCandidate`'s social data into the matched `BusinessLead` without overwriting existing non-null fields.

#### Scenario: Social URL fills empty slot
- **WHEN** a HIGH-confidence match is found and the existing lead has `facebook_url=None` but the candidate has a Facebook URL
- **THEN** the matched lead's `facebook_url` SHALL be updated with the candidate's value

#### Scenario: Existing non-null fields are not overwritten
- **WHEN** a HIGH-confidence match is found and the existing lead already has `phone="+(34)123456"`
- **THEN** the phone SHALL remain unchanged after the merge

### Requirement: Unmatched and low-confidence social candidates are promoted to new leads
The system SHALL create a new `BusinessLead` from any `SocialCandidate` that is `UNMATCHED` or has confidence below `HIGH`, preserving the lead for downstream pipeline stages.

#### Scenario: Unmatched Instagram candidate becomes a new lead
- **WHEN** a `SocialCandidate` from Instagram has `MatchResult(confidence="UNMATCHED")`
- **THEN** a new `BusinessLead` SHALL be created with `lead_source="instagram"`, `match_confidence="UNMATCHED"`, and all fields from the candidate populated

#### Scenario: Partial data is acceptable for social-first leads
- **WHEN** a new lead is created from a social candidate that has no `google_rating` or `address`
- **THEN** those fields SHALL be `None` and the lead SHALL still proceed through scoring and export

### Requirement: Feature flag controls social discovery activation
The system SHALL only activate Instagram and Facebook discovery when `enable_social_discovery: true` is present in the run configuration.

#### Scenario: Social discovery disabled by default
- **WHEN** `enable_social_discovery` is absent or `false` in config
- **THEN** no Instagram or Facebook discovery requests SHALL be made and the pipeline SHALL behave identically to before this change
