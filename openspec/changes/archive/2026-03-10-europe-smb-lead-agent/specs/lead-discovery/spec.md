## ADDED Requirements

### Requirement: Discover businesses via Google Places Text Search
The system SHALL accept an input configuration containing lists of countries, cities, niches, and filter thresholds, and SHALL query the Google Places Text Search API for each niche × city combination to produce a list of candidate business records.

#### Scenario: Generate queries for all niche × city combinations
- **WHEN** the input config contains `niches: ["dentist"]` and `cities: ["Berlin", "Munich"]`
- **THEN** the system SHALL generate and execute two separate queries: `"dentist in Berlin"` and `"dentist in Munich"`

#### Scenario: Respect max_results_per_query limit
- **WHEN** `max_results_per_query` is set to 50
- **THEN** the system SHALL return at most 50 results per niche × city query

#### Scenario: Fetch full Place Details per result
- **WHEN** a candidate `place_id` is returned from Text Search
- **THEN** the system SHALL call Place Details to retrieve: `place_id`, `name`, `formatted_address`, `formatted_phone_number`, `website`, `rating`, `user_ratings_total`, `business_status`, `url` (Maps URL), `types`

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
