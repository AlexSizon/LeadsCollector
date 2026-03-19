## ADDED Requirements

### Requirement: Detect duplicates using four identity keys
The system SHALL consider two business records to be duplicates if they match on at least one of four identity keys: `place_id`, `root_domain`, `normalised_phone`, or high-confidence `normalised_name + city` match.

#### Scenario: Same place_id is a definitive duplicate
- **WHEN** two records share the same non-null `place_id`
- **THEN** they SHALL be treated as duplicates regardless of other field values

#### Scenario: Same root domain is a duplicate signal
- **WHEN** two records share the same non-null `root_domain` (e.g., `smilestudio-berlin.de`)
- **THEN** they SHALL be treated as duplicates

#### Scenario: Same normalised phone is a duplicate signal
- **WHEN** two records share the same non-null normalised phone in E.164 format
- **THEN** they SHALL be treated as duplicates

#### Scenario: High-confidence name + city match is a duplicate signal
- **WHEN** two records share the same `city` AND their `normalised_name` values have a similarity score above the configured threshold (default: Levenshtein similarity ≥ 0.90)
- **THEN** they SHALL be treated as duplicates

### Requirement: Merge duplicate records retaining the richer source
When duplicates are detected, the system SHALL merge them into a single record by retaining the field values from the record with the most non-null fields.

#### Scenario: Richer record wins on merge
- **WHEN** record A has 14 non-null fields and record B has 10 non-null fields and they are detected as duplicates
- **THEN** the merged record SHALL use record A as the base, filling in any additional non-null fields from record B that A lacks

#### Scenario: No second lead record created for a duplicate
- **WHEN** a duplicate is detected and merged
- **THEN** the deduplicator SHALL output exactly one record for that business, not two

### Requirement: Deduplication runs as a post-collection batch pass
The system SHALL run deduplication after all pipeline collection stages are complete for the current run, not during collection.

#### Scenario: Cross-query duplicates are caught
- **WHEN** the same business is returned by both a `"dentist in Berlin"` and `"dentist in Mitte"` query
- **THEN** the deduplication pass SHALL detect and merge the duplicate before export
