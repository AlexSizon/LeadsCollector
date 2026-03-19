## ADDED Requirements

### Requirement: Ingest lead candidates from TripAdvisor discovery
The system SHALL, when `enable_tripadvisor_discovery` is `true` AND the current niche is in the hospitality set, run `TripAdvisorCollector.search()` for each niche × city combination and ingest the returned `SocialCandidate` objects into the candidate pool alongside Instagram and Facebook results.

#### Scenario: TripAdvisor candidates enter cross-source matching
- **WHEN** `enable_tripadvisor_discovery` is `true` and TripAdvisor returns 4 candidates for `"restaurant" in "Lisbon"`
- **THEN** those 4 candidates SHALL enter the cross-source matching step alongside any OSM, Instagram, and Facebook results for the same query

#### Scenario: Non-hospitality niche — TripAdvisor skipped
- **WHEN** the current niche is `"florist"` and `enable_tripadvisor_discovery` is `true`
- **THEN** no TripAdvisor HTTP requests SHALL be made for that query; other collectors run normally

#### Scenario: TripAdvisor failure does not block pipeline
- **WHEN** TripAdvisor discovery returns an empty list for any reason
- **THEN** the pipeline SHALL continue with OSM, Instagram, and Facebook candidates only

## MODIFIED Requirements

### Requirement: Record lead source metadata on every BusinessLead
The system SHALL track the origin of each lead for observability and export.

#### Scenario: OSM-discovered lead tagged correctly
- **WHEN** a lead originates from OSM/Overpass only
- **THEN** `BusinessLead.lead_source` SHALL be `"osm"` and `source_platforms` SHALL be `["osm"]`

#### Scenario: Social-first lead tagged correctly
- **WHEN** a lead is created from an unmatched social candidate
- **THEN** `lead_source` SHALL be the platform name (e.g. `"instagram"`, `"facebook"`, `"tripadvisor"`) and `source_platforms` SHALL contain that platform

#### Scenario: Merged lead reflects all contributing sources
- **WHEN** an OSM lead is enriched by a HIGH-confidence Instagram or TripAdvisor match
- **THEN** `source_platforms` SHALL include all contributing platforms (e.g. `["osm", "instagram"]`, `["osm", "tripadvisor"]`)
