## Why

The current terminal transcript proves that step logging works, but long runs are too noisy for operators: a roughly 200-lead run produced over a thousand terminal lines, most of them per-lead stage traces rather than operator-level progress. We need the terminal log to stay useful during live monitoring while still preserving a path to deeper diagnostics when something goes wrong.

## What Changes

- Add configurable terminal log verbosity modes so operators can choose between concise monitoring output and detailed tracing.
- Add richer query outcome metadata in terminal messages, including retry counts, zero-result classifications, and upstream failure context.
- Add periodic and end-of-run operational summaries, including city-level progress, warning totals, zero-result query counts, website status distribution, and slow-query visibility.
- Add deduplication explainability so the terminal output shows how many leads were removed and sample reasons for removals.
- Preserve shared terminal logging behavior across `src/main.py`, `src/pipeline.py`, and `run_europe_smb.py`.

## Capabilities

### New Capabilities
- `terminal-log-verbosity`: Runtime-selectable terminal logging profiles for operator-friendly output versus detailed tracing.
- `terminal-log-summaries`: Periodic, city-level, and final operational summaries for long-running pipeline scans.

### Modified Capabilities
- `pipeline-run-logging`: Extend terminal progress requirements to include classified query outcomes, dedup explainability, and shared verbosity-aware formatting across entry points.

## Impact

- `src/terminal_logging.py`: Add verbosity controls, summary accumulation, anomaly/output formatting helpers, and dedup explanation helpers.
- `src/pipeline.py` and `run_europe_smb.py`: Emit summary checkpoints, classified query outcomes, and verbosity-aware lead messages.
- `src/main.py`: Accept and pass through verbosity settings to the shared terminal logger.
- Tests and docs: Extend transcript coverage and operator documentation for verbosity modes and summary behavior.
