## ADDED Requirements

### Requirement: Pipeline writes a structured JSONL event log per run
The system SHALL, on every pipeline run, open an append-only JSONL file at `logs/pipeline_<run_id>.jsonl` (creating `logs/` if absent) and write one JSON object per line for each event. The log SHALL be flushed after every write so data is preserved if the process is killed.

#### Scenario: Log file created automatically when logs/ does not exist
- **WHEN** the pipeline starts and `logs/` directory does not exist
- **THEN** `logs/` SHALL be created and the log file SHALL be opened successfully

#### Scenario: Log file named with run timestamp
- **WHEN** a pipeline run starts at `2026-03-18T04:37:26Z`
- **THEN** the log file SHALL be named `logs/pipeline_20260318_043726.jsonl`

#### Scenario: Each log line is valid JSON
- **WHEN** any event is written to the log file
- **THEN** each line SHALL be parseable with `json.loads()` and SHALL contain at minimum an `event` string field, a `ts` ISO-8601 timestamp, and a `run_id` string

#### Scenario: Log file is flushed after each write
- **WHEN** the process is killed mid-run after 500 events have been written
- **THEN** all 500 written events SHALL be present and valid in the log file

### Requirement: Pipeline logs a run_start and run_end event
The system SHALL write a `run_start` event at the beginning of every run and a `run_end` event upon completion, capturing configuration summary and final statistics.

#### Scenario: run_start event contains config summary
- **WHEN** a pipeline run begins
- **THEN** a `run_start` event SHALL be written with fields: `event="run_start"`, `run_id`, `ts`, `config_cities` (list), `config_niches` (list), `config_countries` (list), `max_results_per_query` (int)

#### Scenario: run_end event contains final statistics
- **WHEN** a pipeline run completes (or is interrupted in a finally block)
- **THEN** a `run_end` event SHALL be written with fields: `event="run_end"`, `run_id`, `ts`, `total_leads` (int), `duration_s` (float, wall-clock seconds)

### Requirement: Pipeline logs a query event per niche × city combination
The system SHALL write one `query` event for each niche × city combination attempted, capturing the discovery source used, result count, and wall-clock duration of the Overpass/GooglePlaces call.

#### Scenario: query event written after Overpass search
- **WHEN** the Overpass fallback is used for a niche × city query
- **THEN** a `query` event SHALL be written with `source="overpass"`, `city`, `niche`, `result_count` (int), `duration_s` (float)

#### Scenario: query event written after GooglePlaces search
- **WHEN** GooglePlaces is used successfully for a niche × city query
- **THEN** a `query` event SHALL be written with `source="google_places"`, `city`, `niche`, `result_count` (int), `duration_s` (float)

#### Scenario: query event written with result_count=0 on geocode miss
- **WHEN** Overpass returns no results because Nominatim failed to geocode the city
- **THEN** a `query` event SHALL still be written with `result_count=0` and `source="overpass"` and `error="geocode_failed"` field set

### Requirement: Pipeline logs a lead event per processed lead
The system SHALL write one `lead` event for every `BusinessLead` that completes the enrichment pipeline, capturing website status, which enrichment stages ran, key outcome metrics, and total processing time.

#### Scenario: lead event captures website outcome
- **WHEN** a lead with `website_status == HAS_WEBSITE` is processed
- **THEN** the `lead` event SHALL include `website_status="HAS_WEBSITE"` and `stages.website_fetched=true`

#### Scenario: lead event captures enrichment stage outcomes
- **WHEN** a lead is processed through JSON-LD extraction, contact discovery, and Instagram analysis
- **THEN** the `lead` event SHALL include in its `stages` sub-object: `json_ld_found` (bool), `emails_found` (int), `social_links_found` (int), `instagram_handle_found` (bool), `contact_discovery_run` (bool)

#### Scenario: lead event captures final score and tier
- **WHEN** a lead completes scoring
- **THEN** the `lead` event SHALL include `score` (float, `lead_priority_score`), `tier` (int), and `city` and `niche` fields

#### Scenario: lead event captures processing duration
- **WHEN** a lead finishes all enrichment stages
- **THEN** the `lead` event SHALL include `duration_s` (float) representing wall-clock seconds from lead creation to scoring completion
