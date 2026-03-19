## ADDED Requirements

### Requirement: Export social presence tracking fields in both JSON and CSV formats
The system SHALL include `instagram_presence_status`, `facebook_presence_status`, and `social_discovery_method` fields in both JSON and CSV export outputs. These fields are sourced from the corresponding `BusinessLead` attributes added by the `social-presence-tracking` capability. Their addition SHALL be backward-compatible — all existing fields and column positions in CSV are preserved.

#### Scenario: instagram_presence_status appears in JSON output
- **WHEN** any lead is exported via `export_json()`
- **THEN** the JSON object for each lead SHALL include an `"instagram_presence_status"` key with the string value of the `SocialPresenceStatus` enum (e.g. `"FOUND_ON_WEBSITE"`, `"NOT_FOUND"`, `"UNKNOWN"`)

#### Scenario: facebook_presence_status appears in JSON output
- **WHEN** any lead is exported via `export_json()`
- **THEN** the JSON object for each lead SHALL include a `"facebook_presence_status"` key with the string value of its `SocialPresenceStatus` enum value

#### Scenario: social_discovery_method appears in JSON output
- **WHEN** any lead is exported via `export_json()`
- **THEN** the JSON object for each lead SHALL include a `"social_discovery_method"` key; its value SHALL be the method string (e.g. `"website_html"`, `"json_ld"`, `"hub_resolution"`, `"search_fallback"`) or `null` if undiscovered

#### Scenario: instagram_presence_status appears as a named column in CSV
- **WHEN** a lead is exported via `export_csv()`
- **THEN** the CSV output SHALL include an `instagram_presence_status` column with the string value of the enum

#### Scenario: facebook_presence_status appears as a named column in CSV
- **WHEN** a lead is exported via `export_csv()`
- **THEN** the CSV output SHALL include a `facebook_presence_status` column with the string value of the enum

#### Scenario: social_discovery_method appears as a named column in CSV
- **WHEN** a lead is exported via `export_csv()`
- **THEN** the CSV output SHALL include a `social_discovery_method` column; empty string when `None`

#### Scenario: New columns are appended after existing columns
- **WHEN** the CSV exporter writes output with the new fields
- **THEN** the column positions of all pre-existing columns SHALL remain unchanged; the three new columns SHALL appear at the end of the schema

#### Scenario: Default UNKNOWN value exported for leads processed before tracking was active
- **WHEN** a lead has `instagram_presence_status=SocialPresenceStatus.UNKNOWN` (the default)
- **THEN** the exported value SHALL be the string `"UNKNOWN"` rather than `null` or an empty string
