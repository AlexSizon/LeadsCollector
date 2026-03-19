## ADDED Requirements

### Requirement: Export all BusinessLead fields in both JSON and CSV formats
The system SHALL export all 49 `BusinessLead` fields in both JSON and CSV output formats. The CSV export SHALL NOT be a subset of the JSON export; both formats SHALL contain the same set of fields.

#### Scenario: CSV includes all contact discovery fields
- **WHEN** a lead has `primary_email`, `all_emails`, `primary_phone`, `all_phones`, `whatsapp_links`, `messenger_links`, `booking_links`, `contact_form_urls`, or `primary_contact_method` populated
- **THEN** those values SHALL appear as named columns in the CSV output

#### Scenario: CSV includes all social URL fields
- **WHEN** a lead has any of `instagram_url`, `facebook_url`, `twitter_url`, `tiktok_url`, `linkedin_url`, `youtube_url`, `pinterest_url`, `whatsapp_url`, or `telegram_url` populated
- **THEN** those values SHALL appear as named columns in the CSV output

#### Scenario: CSV includes source attribution fields
- **WHEN** a lead has `lead_source`, `source_platforms`, or `match_confidence` set
- **THEN** those values SHALL appear as named columns in the CSV output

#### Scenario: CSV includes contactability_score
- **WHEN** a lead has a computed `contactability_score`
- **THEN** that value SHALL appear as a named column in the CSV output

#### Scenario: CSV includes guessed_email and map_url
- **WHEN** a lead has `guessed_email` or `map_url` set
- **THEN** those values SHALL appear as named columns in the CSV output

#### Scenario: List fields serialised as pipe-separated strings in CSV
- **WHEN** a list field (e.g., `all_emails`, `whatsapp_links`, `source_platforms`) is exported to CSV
- **THEN** its values SHALL be joined with `|` as separator (matching the existing `issues_found` serialisation pattern)

#### Scenario: Column order is stable across runs
- **WHEN** the CSV exporter writes output
- **THEN** the column order SHALL be deterministic and match the documented schema order regardless of field population

#### Scenario: JSON output is unchanged
- **WHEN** `export_json()` is called
- **THEN** the JSON output SHALL continue to include all fields it currently exports; no fields SHALL be removed
