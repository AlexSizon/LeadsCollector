## ADDED Requirements

### Requirement: SocialPresenceStatus enum tracks how each social profile was discovered
The system SHALL define a `SocialPresenceStatus` string enum in `src/enums.py` with the following values: `FOUND_ON_WEBSITE`, `FOUND_IN_SCHEMA`, `FOUND_VIA_HUB`, `FOUND_VIA_SEARCH`, `NOT_FOUND`, `UNKNOWN`. This enum SHALL be used to record the provenance of discovered social profile URLs on a per-platform basis.

#### Scenario: Enum values are strings compatible with JSON serialisation
- **WHEN** a `SocialPresenceStatus` value is serialised to JSON
- **THEN** it SHALL produce a plain string (e.g. `"FOUND_ON_WEBSITE"`) without requiring a custom encoder

#### Scenario: Default value is UNKNOWN
- **WHEN** a `BusinessLead` is created without explicit social presence tracking
- **THEN** `instagram_presence_status` and `facebook_presence_status` SHALL both default to `SocialPresenceStatus.UNKNOWN`

### Requirement: BusinessLead stores per-platform social presence status
The `BusinessLead` model SHALL include `instagram_presence_status` (type `SocialPresenceStatus`, default `UNKNOWN`) and `facebook_presence_status` (type `SocialPresenceStatus`, default `UNKNOWN`) fields. These fields record HOW the social URL for each platform was discovered, not whether the account is active.

#### Scenario: FOUND_ON_WEBSITE set when instagram_url extracted from website HTML
- **WHEN** `SocialCollector.extract_from_html()` finds an instagram.com link in the website HTML and that URL is written to `lead.instagram_url`
- **THEN** `lead.instagram_presence_status` SHALL be set to `SocialPresenceStatus.FOUND_ON_WEBSITE`

#### Scenario: FOUND_IN_SCHEMA set when instagram_url extracted from JSON-LD sameAs
- **WHEN** `json_ld_extractor.extract_from_html()` finds an instagram.com URL in a `sameAs` array and populates `lead.instagram_url`
- **THEN** `lead.instagram_presence_status` SHALL be set to `SocialPresenceStatus.FOUND_IN_SCHEMA`

#### Scenario: FOUND_VIA_HUB set when instagram_url extracted from Linktree or link hub
- **WHEN** a Linktree/hub page is fetched and `SocialCollector` finds an instagram.com link on that hub page
- **THEN** `lead.instagram_presence_status` SHALL be set to `SocialPresenceStatus.FOUND_VIA_HUB`

#### Scenario: FOUND_VIA_SEARCH set when instagram_url populated from search-based discovery
- **WHEN** `InstagramDiscoveryCollector` or `CrossSourceMatcher` merges an Instagram URL from a search-based `SocialCandidate` into the lead
- **THEN** `lead.instagram_presence_status` SHALL be set to `SocialPresenceStatus.FOUND_VIA_SEARCH`

#### Scenario: NOT_FOUND set when all Instagram discovery sources are exhausted
- **WHEN** website extraction, JSON-LD extraction, hub resolution, and (if active) search discovery all produce no Instagram URL for a lead
- **THEN** `lead.instagram_presence_status` SHALL be set to `SocialPresenceStatus.NOT_FOUND`

#### Scenario: Facebook presence status tracks the same provenance for Facebook
- **WHEN** `lead.facebook_url` is populated by any discovery source
- **THEN** `lead.facebook_presence_status` SHALL be set to the corresponding `SocialPresenceStatus` value matching the source that populated it (`FOUND_ON_WEBSITE`, `FOUND_IN_SCHEMA`, `FOUND_VIA_HUB`, or `FOUND_VIA_SEARCH`)

#### Scenario: Higher-confidence source wins when multiple sources find the same platform
- **WHEN** `lead.instagram_url` is already set from website HTML (`FOUND_ON_WEBSITE`) and search-based discovery later also finds an Instagram URL
- **THEN** `lead.instagram_presence_status` SHALL remain `FOUND_ON_WEBSITE` (website source is higher confidence and already satisfied)

### Requirement: BusinessLead stores a social_discovery_method string field
The `BusinessLead` model SHALL include a `social_discovery_method: Optional[str]` field (default `None`) that records a human-readable description of the most significant discovery path that contributed to the lead's social data. This field is informational and intended for debugging and reporting.

#### Scenario: social_discovery_method set on leads enriched through website extraction
- **WHEN** social URLs are discovered from the business website HTML
- **THEN** `lead.social_discovery_method` SHALL be set to `"website_html"` (unless a higher-fidelity source like `json_ld` has already set it)

#### Scenario: social_discovery_method set to json_ld when sameAs yields discovery
- **WHEN** social URLs are discovered from JSON-LD `sameAs` fields
- **THEN** `lead.social_discovery_method` SHALL be set to `"json_ld"`

#### Scenario: social_discovery_method set to hub when link hub is followed
- **WHEN** social URLs are discovered via Linktree/hub resolution
- **THEN** `lead.social_discovery_method` SHALL be set to `"hub_resolution"`

#### Scenario: social_discovery_method set to search for search-fallback leads
- **WHEN** the only social discovery that contributed for a lead came from `InstagramDiscoveryCollector` or `FacebookDiscoveryCollector`
- **THEN** `lead.social_discovery_method` SHALL be set to `"search_fallback"`

#### Scenario: social_discovery_method remains None when no social URLs found
- **WHEN** no social URLs are discovered for a lead from any source
- **THEN** `lead.social_discovery_method` SHALL remain `None`
