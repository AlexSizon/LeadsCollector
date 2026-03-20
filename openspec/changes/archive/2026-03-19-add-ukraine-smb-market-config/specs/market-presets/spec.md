## ADDED Requirements

### Requirement: Repository provides a bundled Ukraine SMB market preset
The repository SHALL include a dedicated configuration preset for Ukraine at `config/run_ukraine_smb.json` so operators can run a Ukraine-focused SMB lead scan without editing an existing Europe preset.

#### Scenario: Ukraine preset file is present
- **WHEN** an operator lists bundled run presets in `config/`
- **THEN** the repository SHALL contain `config/run_ukraine_smb.json`

#### Scenario: Ukraine preset targets the requested cities
- **WHEN** `config/run_ukraine_smb.json` is loaded
- **THEN** it SHALL define `countries: ["Ukraine"]`
- **AND** it SHALL define `cities` containing exactly `["Kyiv", "Lviv", "Kharkiv", "Odesa", "Ivano-Frankivsk"]`
- **AND** it SHALL define `city_country_map` entries mapping each configured city to `"Ukraine"`

### Requirement: Ukraine preset uses supported high-opportunity SMB niches
The Ukraine preset SHALL define a niche list that is both commercially attractive for website sales or website improvement outreach and compatible with the current Overpass niche normalization used by the repository.

#### Scenario: Ukraine preset uses curated supported niches
- **WHEN** `config/run_ukraine_smb.json` is loaded
- **THEN** its `niches` field SHALL contain exactly `["beauty salon", "restaurant", "bakery", "florist", "boutique", "cosmetics shop", "pet shop", "home decor shop"]`

#### Scenario: Preset avoids unsupported service niches
- **WHEN** the preset is executed without a Google Places API key and the Overpass fallback is used
- **THEN** every configured niche SHALL map to an existing canonical niche supported by `src/collectors/overpass_collector.py`

### Requirement: Ukraine preset includes ready-to-run campaign defaults
The Ukraine preset SHALL include explicit runtime defaults that support website-sales lead generation, preserve broad discovery coverage, and isolate outputs from other bundled market runs.

#### Scenario: Preset uses outreach-oriented discovery defaults
- **WHEN** `config/run_ukraine_smb.json` is loaded
- **THEN** it SHALL define `language_priority` as `["uk", "en", "ru"]`
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
