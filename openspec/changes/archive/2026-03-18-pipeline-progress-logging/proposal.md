## Why

The pipeline runs for 7+ hours with no persistent record of what happened per query — only ephemeral stdout. After a run it's impossible to know which cities returned few results, which websites timed out, which niches have low OSM coverage, or how long each stage took per lead. Without this data there's no way to tune queries, timeouts, or niche mappings.

## What Changes

- **New**: Structured JSONL log written to `logs/pipeline_<timestamp>.jsonl` during every pipeline run (both `src/pipeline.py` and `run_europe_smb.py`)
- **New**: One log record per lead processed, capturing all per-lead stage timings and outcomes
- **New**: Run-level summary record written at pipeline start and end (query counts, city/niche totals, duration)
- **New**: Per-query record capturing Overpass/GooglePlaces result count, geocode success/failure, query duration
- **Modified**: `logs/` directory auto-created if missing; old log files preserved (not overwritten)
- **New**: `analyze_log.py` CLI tool that reads a JSONL log and prints a structured analysis report (slowest queries, coverage gaps, stage timing breakdown, error summary)

## Capabilities

### New Capabilities
- `pipeline-run-logging`: Structured JSONL event log written by the pipeline capturing per-query, per-lead, and run-level events with timing and outcome metadata
- `log-analyzer`: CLI tool (`analyze_log.py`) that reads a pipeline JSONL log and produces a human-readable analysis report

### Modified Capabilities
- `lead-discovery`: Pipeline discovery stage now emits structured log events per query (result count, source used, duration) — requirement added to the spec

## Impact

- `src/pipeline.py`: Add `PipelineLogger` calls at run start/end, per query, per lead stage
- `run_europe_smb.py`: Same logging integration
- `logs/`: New output directory (gitignored or included — by convention alongside `output/`)
- `analyze_log.py`: New root-level script (like `run_europe_smb.py`)
- No breaking changes to existing output formats or API
