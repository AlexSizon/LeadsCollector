## ADDED Requirements

### Requirement: Pipeline emits rolling operational summaries during long runs
The system SHALL emit aggregated terminal summaries during long-running scans so operators can understand progress and upstream health without manually scanning hundreds of individual log lines.

#### Scenario: City completion summary is emitted
- **WHEN** all configured niches for a city have finished
- **THEN** the terminal SHALL emit a city-level summary including completed query count, leads found before deduplication, zero-result queries, and warning or retry counts for that city

#### Scenario: Periodic health snapshot is emitted during long runs
- **WHEN** a run crosses a configured progress checkpoint such as every N completed queries
- **THEN** the terminal SHALL emit a health snapshot including completed queries, total warnings, zero-result query count, and slow-query visibility

### Requirement: Pipeline emits a final operational summary before export completion
The system SHALL emit an operator-focused end-of-run summary before export completion so the transcript captures the most important runtime outcomes in one place.

#### Scenario: Final summary includes runtime health and output quality
- **WHEN** a run completes processing before export finishes
- **THEN** the terminal SHALL emit a final summary including total duration, total warnings, zero-result query count, website-status distribution, and the slowest queries

#### Scenario: Deduplication summary explains removals
- **WHEN** deduplication removes duplicate leads
- **THEN** the terminal SHALL report the number of removed leads and include a concise sample of duplicate-removal reasons or signals
