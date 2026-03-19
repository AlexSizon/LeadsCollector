## ADDED Requirements

### Requirement: Pipeline supports configurable terminal log verbosity
The system SHALL allow operators to choose a terminal log verbosity profile for each run so they can optimize for live monitoring or detailed troubleshooting without changing code.

#### Scenario: Normal verbosity favors operator overview
- **WHEN** a pipeline run uses the default terminal verbosity
- **THEN** the terminal SHALL prioritize run, query, anomaly, deduplication, and export messages while suppressing routine per-lead stage traces

#### Scenario: Verbose verbosity includes lead-level tracing
- **WHEN** a pipeline run uses verbose terminal verbosity
- **THEN** the terminal SHALL include detailed per-lead stage progress in addition to the operator-level run and query messages

#### Scenario: Verbosity is selected consistently across entry points
- **WHEN** the user chooses a terminal verbosity setting for either pipeline entry point
- **THEN** the selected verbosity SHALL control terminal output behavior through the same shared logger implementation

### Requirement: Important anomalies remain visible in concise modes
The system SHALL keep operator-relevant anomalies visible even when verbose lead tracing is suppressed.

#### Scenario: Zero-result or upstream-failure queries surface in normal mode
- **WHEN** a query completes with zero results after retries or due to upstream failure conditions
- **THEN** the terminal SHALL emit an explicit anomaly-visible message in normal verbosity instead of hiding the outcome inside suppressed detailed logs

#### Scenario: Unexpected website outcomes surface in normal mode
- **WHEN** lead processing encounters operator-relevant states such as `UNKNOWN` or `BROKEN_WEBSITE`
- **THEN** the terminal SHALL emit a concise anomaly-visible message even if routine lead-stage messages are otherwise suppressed
