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

## MODIFIED Requirements

### Requirement: Discover businesses via Google Places Text Search
The system SHALL accept an input configuration containing lists of countries, cities, niches, and filter thresholds, and SHALL query the Google Places Text Search API for each niche × city combination to produce a list of candidate business records. Each produced `BusinessLead` SHALL include an `instagram_url` field (type `Optional[str]`, default `None`) populated from any available source (SocialCollector HTML extraction, cross-source match merge, or Google Places data).

#### Scenario: Generate queries for all niche × city combinations
- **WHEN** the input config contains `niches: ["dentist"]` and `cities: ["Berlin", "Munich"]`
- **THEN** the system SHALL generate and execute two separate queries: `"dentist in Berlin"` and `"dentist in Munich"`

#### Scenario: Respect max_results_per_query limit
- **WHEN** `max_results_per_query` is set to 50
- **THEN** the system SHALL return at most 50 results per niche × city query

#### Scenario: Fetch full Place Details per result
- **WHEN** a candidate `place_id` is returned from Text Search
- **THEN** the system SHALL call Place Details to retrieve: `place_id`, `name`, `formatted_address`, `formatted_phone_number`, `website`, `rating`, `user_ratings_total`, `business_status`, `url` (Maps URL), `types`

#### Scenario: BusinessLead output includes instagram_url field
- **WHEN** a `BusinessLead` is produced by any pipeline entry point
- **THEN** the lead SHALL have an `instagram_url` attribute of type `Optional[str]`; it SHALL be populated if an Instagram URL can be found and `None` otherwise
