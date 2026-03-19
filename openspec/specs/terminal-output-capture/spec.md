## ADDED Requirements

### Requirement: Pipeline persists a terminal transcript for each run
The system SHALL, on every pipeline run, save the human-readable terminal stdout/stderr stream to a timestamped log file that can be reviewed after the run completes.

#### Scenario: Transcript file created automatically
- **WHEN** a pipeline run starts
- **THEN** the system SHALL create a terminal transcript file for that run under the project's logging/output area without requiring manual shell redirection

#### Scenario: Transcript file correlates with structured run logs
- **WHEN** a run already has a `run_id` used by structured JSONL logging
- **THEN** the terminal transcript filename SHALL use the same run identity so operators can correlate terminal output with structured events

#### Scenario: Transcript remains readable after run completion
- **WHEN** a run finishes successfully or with an error
- **THEN** the transcript file SHALL contain the terminal messages emitted during that run in human-readable text form
