## Why

The pipeline now writes structured JSONL logs, but operators still have poor live visibility during long runs because terminal output is sparse, inconsistent between entry points, and not persisted as a readable execution transcript. We need clearer per-step terminal progress and a saved terminal log so runs can be monitored in real time and reviewed without parsing JSONL manually.

## What Changes

- Add persistent terminal-session logging so pipeline stdout/stderr can be saved to a timestamped log file per run.
- Add explicit terminal progress messages for each major pipeline stage, including run start, query execution, lead enrichment stages, deduplication, and export completion.
- Standardize the live terminal logging behavior across `src/pipeline.py`, `src/main.py`, and `run_europe_smb.py` so operators see the same step vocabulary regardless of entry point.
- Keep the existing JSONL event log as the structured telemetry source; this change improves human-readable runtime feedback rather than replacing the file logger.

## Capabilities

### New Capabilities
- `terminal-output-capture`: Persist human-readable terminal stdout/stderr for each pipeline run in a timestamped log file.

### Modified Capabilities
- `pipeline-run-logging`: Extend runtime logging requirements so each major pipeline step emits clear terminal progress messages during execution.

## Impact

- `src/pipeline.py`: Add consistent stage-level terminal logging around query discovery, enrichment, scoring, and deduplication.
- `run_europe_smb.py`: Align terminal progress output with the main pipeline implementation.
- `src/main.py`: Ensure top-level execution and export steps are clearly logged in the terminal.
- Logging/output conventions: introduce a persisted terminal log path alongside the existing structured JSONL run logs.
