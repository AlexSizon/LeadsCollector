## ADDED Requirements

### Requirement: BusinessLead stores an instagram_url field
The `BusinessLead` output model SHALL include an `instagram_url` field of type `Optional[str]`, defaulting to `None`, to store the publicly known Instagram profile URL for the business.

#### Scenario: instagram_url populated from SocialCollector HTML extraction
- **WHEN** `SocialCollector.extract_from_html()` finds a link to `instagram.com/<handle>` in website HTML
- **THEN** the extracted Instagram URL SHALL be written to `lead.instagram_url`

#### Scenario: instagram_url populated from SocialCollector OSM tags
- **WHEN** a business OSM record contains a `contact:instagram` tag
- **THEN** the extracted Instagram URL SHALL be written to `lead.instagram_url`

#### Scenario: instagram_url populated from CrossSourceMatcher merge
- **WHEN** `CrossSourceMatcher.merge_into()` merges a `SocialCandidate` with `source_platform="instagram"` into an existing `BusinessLead`
- **THEN** the candidate's social URL SHALL be written to `lead.instagram_url` if `lead.instagram_url` is currently `None`

#### Scenario: instagram_url used as matching signal in CrossSourceMatcher
- **WHEN** `CrossSourceMatcher.match()` evaluates a candidate against existing leads
- **THEN** an exact domain match between the candidate's Instagram URL and a lead's `instagram_url` SHALL count as a social match signal, increasing match confidence

### Requirement: LeadPipeline supports contact discovery and contactability scoring for Google Places leads
The `LeadPipeline` (in `src/pipeline.py`) SHALL, when `enable_contact_discovery` is `true` in the input config, run `ContactDiscovery.extract()` on each lead that has a working website and apply the result to the lead; it SHALL then compute `contactability_score` using `compute_contactability_score()` and pass it to `compute_final_score()`.

#### Scenario: Contact discovery runs on Google Places leads with a website
- **WHEN** a Google Places lead has `website_status == HAS_WEBSITE` and `enable_contact_discovery` is `true`
- **THEN** `ContactDiscovery.extract()` SHALL be called with the lead and the website HTTP response, and `ContactDiscovery.apply_to_lead()` SHALL write results back to the lead

#### Scenario: Contactability score computed and included in final score
- **WHEN** `enable_contact_discovery` is `true`
- **THEN** `compute_contactability_score(lead)` SHALL be called and its return value SHALL be passed as the `contactability` argument to `compute_final_score()`

#### Scenario: Contact discovery skipped when flag is false
- **WHEN** `enable_contact_discovery` is `false` (or absent from config)
- **THEN** `ContactDiscovery` SHALL NOT be called and `contactability_score` SHALL remain `0.0`

### Requirement: LeadPipeline supports social discovery and cross-source matching
The `LeadPipeline` SHALL, when `enable_social_discovery` is `true` in the input config, run `InstagramDiscoveryCollector` and `FacebookDiscoveryCollector` per niche × city combination, match discovered social candidates against the existing lead list using `CrossSourceMatcher`, merge matched candidates into existing leads, and preserve unmatched candidates as stub `BusinessLead` entries with `lead_source` set to the candidate's platform.

#### Scenario: Social discovery results are merged into existing Google Places leads
- **WHEN** `InstagramDiscoveryCollector.search()` returns a `SocialCandidate` whose name and city closely match an existing lead with confidence HIGH
- **THEN** `CrossSourceMatcher.merge_into()` SHALL enrich the existing lead with social data (social URLs, phone, email) without overwriting non-null fields

#### Scenario: Unmatched social candidates are preserved as stub leads
- **WHEN** a `SocialCandidate` does not match any existing lead with HIGH confidence
- **THEN** a minimal `BusinessLead` stub SHALL be created from the candidate and appended to the leads list, with `lead_source` set to the candidate's `source_platform`

#### Scenario: Social discovery skipped when flag is false
- **WHEN** `enable_social_discovery` is `false`
- **THEN** no social collectors SHALL be called and no social stubs SHALL be created

### Requirement: Discover businesses via Google Places Text Search
The system SHALL accept an input configuration containing lists of countries, cities, niches, filter thresholds, and an optional `search_languages` field, and SHALL query discovery sources for each applicable niche × city × search-language combination to produce a list of candidate business records. Each produced `BusinessLead` SHALL include an `instagram_url` field (type `Optional[str]`, default `None`) populated from any available source (SocialCollector HTML extraction, cross-source match merge, or Google Places data).

#### Scenario: Generate queries for all niche × city combinations
- **WHEN** the input config contains `niches: ["dentist"]`, `cities: ["Berlin", "Munich"]`, and no `search_languages`
- **THEN** the system SHALL generate and execute two separate queries using the canonical niche label: `"dentist in Berlin"` and `"dentist in Munich"`

#### Scenario: Generate multilingual queries for configured search languages
- **WHEN** the input config contains `niches: ["restaurant"]`, `cities: ["Kyiv"]`, and `search_languages: ["en", "uk", "ru"]`
- **THEN** the system SHALL generate one query per configured search language using localized niche search phrases for that canonical niche
- **AND** each query SHALL still be attributed to the canonical niche `"restaurant"` in downstream processing

#### Scenario: Respect max_results_per_query limit
- **WHEN** `max_results_per_query` is set to 50
- **THEN** the system SHALL return at most 50 results per executed niche × city × search-language query

#### Scenario: Fetch full Place Details per result
- **WHEN** a candidate `place_id` is returned from Text Search
- **THEN** the system SHALL call Place Details to retrieve: `place_id`, `name`, `formatted_address`, `formatted_phone_number`, `website`, `rating`, `user_ratings_total`, `business_status`, `url` (Maps URL), `types`

#### Scenario: BusinessLead output includes instagram_url field
- **WHEN** a `BusinessLead` is produced by any pipeline entry point
- **THEN** the lead SHALL have an `instagram_url` attribute of type `Optional[str]`; it SHALL be populated if an Instagram URL can be found and `None` otherwise

### Requirement: Filter out ineligible businesses at collection time
The system SHALL exclude businesses from collection results that do not meet the configured quality thresholds or eligibility criteria.

#### Scenario: Exclude permanently closed businesses
- **WHEN** a Place Details response contains `business_status: "PERMANENTLY_CLOSED"`
- **THEN** the system SHALL exclude that record from the output

#### Scenario: Enforce minimum reviews threshold
- **WHEN** `min_reviews_threshold` is set to 20 and a business has `user_ratings_total` < 20
- **THEN** the system SHALL exclude that business from the output

#### Scenario: Enforce minimum rating threshold
- **WHEN** `min_rating_threshold` is set to 4.0 and a business has `rating` < 4.0
- **THEN** the system SHALL exclude that business from the output

### Requirement: Persist raw discovery fields per business record
The system SHALL store a defined set of raw fields for each collected business before enrichment.

#### Scenario: All required fields captured
- **WHEN** a business passes all filters
- **THEN** the system SHALL store: `place_id`, `company_name`, `category`, `address`, `city`, `country`, `phone`, `website_url`, `rating`, `reviews_count`, `map_url`, `business_status`

#### Scenario: Missing optional fields default to null
- **WHEN** a Place Details response does not include `website` or `formatted_phone_number`
- **THEN** the system SHALL store `null` for those fields rather than omitting them

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

### Requirement: Lead discovery pipeline emits structured log events per query
The lead discovery stage SHALL, when a `PipelineLogger` is active, emit one `query` log event per executed niche × city × search-language query, capturing the data source used, result count, wall-clock duration of the search call, and the active search language. This applies to both `src/pipeline.py` (LeadPipeline) and `run_europe_smb.py`.

#### Scenario: Query event emitted after successful Overpass search in LeadPipeline
- **WHEN** `LeadPipeline.run()` completes an Overpass search for an executed niche × city × search-language query
- **THEN** a `query` event SHALL be written to the active `PipelineLogger` with `source="overpass"`, `city`, `niche`, `search_language`, `result_count`, and `duration_s`

#### Scenario: Query event emitted after GooglePlaces fallback failure
- **WHEN** GooglePlaces raises an exception and Overpass is used as fallback in `LeadPipeline.run()`
- **THEN** the `query` event SHALL have `source="overpass"` and SHALL also include `fallback=true`

#### Scenario: Query event emitted in run_europe_smb.py
- **WHEN** `run_europe_smb.py` completes an Overpass search for an executed niche × city × search-language query
- **THEN** a `query` event SHALL be emitted to the same `PipelineLogger` instance used for the run and SHALL include `search_language`
