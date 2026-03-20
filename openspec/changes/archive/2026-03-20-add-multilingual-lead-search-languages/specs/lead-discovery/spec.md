## MODIFIED Requirements

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
