## ADDED Requirements

### Requirement: analyze_log.py reads a pipeline JSONL log and prints a structured analysis report
The system SHALL provide a `analyze_log.py` script at the project root that accepts an optional path argument (defaulting to the most recent file in `logs/`), reads all events, and prints a human-readable analysis report to stdout.

#### Scenario: Default invocation uses most recent log file
- **WHEN** `python analyze_log.py` is run with no arguments and `logs/` contains one or more JSONL files
- **THEN** the script SHALL load the most recent file (by filename sort, which is also chronological) and print the analysis

#### Scenario: Explicit path argument accepted
- **WHEN** `python analyze_log.py logs/pipeline_20260318_043726.jsonl` is run
- **THEN** the script SHALL load exactly that file and print the analysis

#### Scenario: Error when no log files found
- **WHEN** `python analyze_log.py` is run and `logs/` is empty or does not exist
- **THEN** the script SHALL print an informative error message and exit with code 1

### Requirement: Analysis report includes Run Summary section
The system SHALL include a Run Summary section showing top-level run metadata.

#### Scenario: Run Summary shows duration, lead count, and city/niche counts
- **WHEN** a log file containing `run_start` and `run_end` events is analysed
- **THEN** the report SHALL show: `run_id`, start timestamp, total duration (formatted as `Xh Ym`), total leads, number of cities, number of niches

### Requirement: Analysis report includes Query Coverage section
The system SHALL include a Query Coverage section identifying searches with low or zero results.

#### Scenario: Zero-result queries are listed
- **WHEN** the log contains `query` events with `result_count=0`
- **THEN** the report SHALL list each such query showing `city`, `niche`, `source`, and `error` (if present)

#### Scenario: Slowest queries are listed in descending order
- **WHEN** the log contains two or more `query` events
- **THEN** the report SHALL list the 10 slowest queries by `duration_s` in descending order, showing city, niche, source, result_count, and duration

### Requirement: Analysis report includes Stage Coverage section
The system SHALL include a Stage Coverage section showing what fraction of leads had each enrichment stage run successfully.

#### Scenario: Website status breakdown shown
- **WHEN** the log contains `lead` events
- **THEN** the report SHALL show counts and percentages for each `website_status` value (`HAS_WEBSITE`, `NO_WEBSITE`, `BROKEN_WEBSITE`, `UNKNOWN`)

#### Scenario: Enrichment stage coverage rates shown
- **WHEN** the log contains `lead` events with `stages` sub-objects
- **THEN** the report SHALL show, for each tracked stage field (`json_ld_found`, `emails_found > 0`, `instagram_handle_found`, `contact_discovery_run`), the count and percentage of leads where that stage produced a positive result

### Requirement: Analysis report includes Score Distribution section
The system SHALL include a Score Distribution section showing how leads are distributed across tiers and score ranges.

#### Scenario: Tier distribution shown
- **WHEN** the log contains `lead` events with `tier` fields
- **THEN** the report SHALL show the count of leads per tier (1–4)

#### Scenario: Average scores shown per city
- **WHEN** the log contains `lead` events with `score` and `city` fields
- **THEN** the report SHALL show, for each city, the count of leads and average `lead_priority_score`, sorted descending by average score
