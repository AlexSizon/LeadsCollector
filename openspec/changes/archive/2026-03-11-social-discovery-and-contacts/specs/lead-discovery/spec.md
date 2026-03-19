## ADDED Requirements

### Requirement: Ingest lead candidates from Instagram discovery
The system SHALL, when `enable_social_discovery` is `true`, run `InstagramDiscoveryCollector.search()` for each niche × city combination and ingest the returned `SocialCandidate` objects into the unified candidate pool.

#### Scenario: Instagram candidates added to pool
- **WHEN** `enable_social_discovery` is `true` and Instagram discovery returns 5 candidates for `"restaurant" in "Madrid"`
- **THEN** those 5 candidates SHALL enter the cross-source matching step alongside any OSM results for the same query

#### Scenario: Zero Instagram results do not block pipeline
- **WHEN** Instagram discovery returns an empty list for a query
- **THEN** the OSM-sourced candidates for that query SHALL continue through the pipeline unaffected

### Requirement: Ingest lead candidates from Facebook discovery
The system SHALL, when `enable_social_discovery` is `true`, run `FacebookDiscoveryCollector.search()` for each niche × city combination and ingest the returned `SocialCandidate` objects into the unified candidate pool.

#### Scenario: Facebook candidates added to pool
- **WHEN** `enable_social_discovery` is `true` and Facebook discovery returns 3 candidates
- **THEN** those candidates SHALL enter cross-source matching alongside OSM results

#### Scenario: Zero Facebook results do not block pipeline
- **WHEN** Facebook discovery is unreachable
- **THEN** the pipeline SHALL continue with OSM and Instagram candidates only

### Requirement: Perform cross-source matching before BusinessLead creation
The system SHALL, after collecting candidates from all active sources for a query, run `CrossSourceMatcher` to merge social candidates into existing leads or promote them to new leads before any downstream enrichment.

#### Scenario: HIGH-confidence social candidate merged into existing lead
- **WHEN** a social candidate matches an existing `BusinessLead` with `HIGH` confidence
- **THEN** the candidate's social data SHALL be merged into that lead and no duplicate lead SHALL be created

#### Scenario: UNMATCHED social candidate becomes a new lead
- **WHEN** a social candidate has `MatchResult(confidence="UNMATCHED")`
- **THEN** a new `BusinessLead` SHALL be created and appended to the leads list with `lead_source` set to the candidate's `source_platform`

### Requirement: Record lead source metadata on every BusinessLead
The system SHALL track the origin of each lead for observability and export.

#### Scenario: OSM-discovered lead tagged correctly
- **WHEN** a lead originates from OSM/Overpass only
- **THEN** `BusinessLead.lead_source` SHALL be `"osm"` and `source_platforms` SHALL be `["osm"]`

#### Scenario: Social-first lead tagged correctly
- **WHEN** a lead is created from an unmatched social candidate
- **THEN** `lead_source` SHALL be the platform name (e.g. `"instagram"`) and `source_platforms` SHALL contain that platform

#### Scenario: Merged lead reflects all contributing sources
- **WHEN** an OSM lead is enriched by a HIGH-confidence Instagram match
- **THEN** `source_platforms` SHALL be `["osm", "instagram"]`
