## MODIFIED Requirements

### Requirement: Ukraine preset includes ready-to-run campaign defaults
The Ukraine preset SHALL include explicit runtime defaults that support website-sales lead generation, preserve broad discovery coverage, and isolate outputs from other bundled market runs.

#### Scenario: Preset uses outreach-oriented discovery defaults
- **WHEN** `config/run_ukraine_smb.json` is loaded
- **THEN** it SHALL define `language_priority` as `["uk", "en", "ru"]`
- **AND** it SHALL define `search_languages` as `["en", "uk", "ru"]`
- **AND** it SHALL define `max_results_per_query` with a value greater than `0`
- **AND** it SHALL define `min_reviews_threshold` as `0`
- **AND** it SHALL define `min_rating_threshold` as `0.0`
- **AND** it SHALL enable `include_instagram_analysis`
- **AND** it SHALL enable `run_website_audit`
- **AND** it SHALL enable `enable_social_discovery`
- **AND** it SHALL enable `enable_contact_discovery`
- **AND** it SHALL enable `enable_tripadvisor_discovery`
- **AND** it SHALL enable `enable_email_guesser`

#### Scenario: Preset writes outputs to dedicated Ukraine files
- **WHEN** `config/run_ukraine_smb.json` is loaded
- **THEN** its `output.json`, `output.csv`, and `output.summary` values SHALL point to Ukraine-specific artifact paths that do not overwrite the existing Europe preset outputs
