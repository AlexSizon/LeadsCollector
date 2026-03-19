## ADDED Requirements

### Requirement: Pipeline emits human-readable terminal progress for major steps
The system SHALL emit concise terminal log messages for each major pipeline step so operators can follow long-running scans in real time without reading the structured JSONL file directly.

#### Scenario: Run start announces execution plan
- **WHEN** a pipeline run begins
- **THEN** the terminal SHALL show a run-start message including the active config scope such as cities, niches, total queries, and the locations of the runtime log outputs

#### Scenario: Query execution logs step progress
- **WHEN** a niche × city query starts and completes
- **THEN** the terminal SHALL show the query step name, the city/niche being processed, the source used, and the completion outcome including result count or error/fallback state

#### Scenario: Batch completion logs terminal summary
- **WHEN** a major batch step such as deduplication or export starts or finishes
- **THEN** the terminal SHALL emit a summary message describing that step and its result counts or output paths

### Requirement: Terminal step logging is consistent across pipeline entry points
The system SHALL use the same terminal step vocabulary and formatting conventions in both `src/main.py`/`src/pipeline.py` and `run_europe_smb.py`.

#### Scenario: Main pipeline entry point uses shared step messages
- **WHEN** the user runs the pipeline through `src/main.py`
- **THEN** terminal messages for run start, query progress, lead processing, deduplication, and export SHALL follow the shared format

#### Scenario: OSM runner uses shared step messages
- **WHEN** the user runs the pipeline through `run_europe_smb.py`
- **THEN** terminal messages for the same major steps SHALL follow the same shared format instead of a divergent ad hoc style
