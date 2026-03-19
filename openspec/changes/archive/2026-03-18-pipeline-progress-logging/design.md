## Context

The pipeline runs for 4–8 hours per full Europe SMB scan. It produces output JSON/CSV but discards all execution telemetry — no record of which queries ran, how many results each returned, how long each stage took, or which leads failed enrichment. The only diagnostic path is re-running from scratch or reading the ephemeral stdout stream.

Two entry points exist: `src/pipeline.py` (`LeadPipeline` class, used by `src/main.py`) and `run_europe_smb.py` (standalone script with its own loop). Both need the same logging behaviour.

The `logs/` directory exists in the workspace but is empty.

## Goals / Non-Goals

**Goals:**
- Append-only JSONL log written to `logs/pipeline_<timestamp>.jsonl` automatically on every run
- Capture per-query events (city, niche, source used, result count, duration)
- Capture per-lead events (website status, stages run, enrichment outcomes, final score, processing time)
- Capture run-level open/close events (config summary, total duration, lead count)
- `analyze_log.py` CLI tool: reads a JSONL log, prints analysis (coverage gaps, slowest queries, stage timing, error rate)
- Zero impact on existing outputs (leads.json, leads.csv) and no changes to scoring logic
- Works the same for both `src/pipeline.py` and `run_europe_smb.py`

**Non-Goals:**
- Real-time dashboard or streaming metrics
- Log rotation or size management (left to the operator)
- Changing any existing stage logic or scoring
- Centralised log aggregation or remote storage

## Decisions

### D1 — JSONL format (one JSON object per line)

Chosen over: plain text, CSV, SQLite.

JSONL is append-friendly (write one line per event, no file locking), trivially parseable with `json.loads()`, schema-flexible (different event types can have different fields), and grep-friendly. SQLite would require a schema and connection management. CSV doesn't support nested data (e.g., per-stage timings dict).

Each line is one event object with a mandatory `event` type field:
```json
{"event": "run_start", "ts": "2026-03-18T04:37:26Z", "run_id": "20260318_043726", ...}
{"event": "query", "ts": "...", "run_id": "...", "city": "Madrid", "niche": "restaurant", "source": "overpass", "result_count": 28, "duration_s": 62.1}
{"event": "lead", "ts": "...", "run_id": "...", "company": "...", "city": "Madrid", "website_status": "HAS_WEBSITE", "stages": {...}, "score": 42.0, "duration_s": 4.2}
{"event": "run_end", "ts": "...", "run_id": "...", "total_leads": 3759, "duration_s": 26640}
```

### D2 — `PipelineLogger` class in `src/logging_utils.py`

A lightweight class wrapping `open()` in append mode. Methods: `log_run_start()`, `log_query()`, `log_lead()`, `log_run_end()`. Not a subclass of Python's `logging.Logger` — keeps the two concerns separate and avoids `logging` module config complexity.

`PipelineLogger` is instantiated once per run and passed to the pipeline methods, or stored on `self` in `LeadPipeline`. Both entry points construct it the same way.

Chosen over: monkey-patching Python's `logging` module with a `FileHandler`, which would mix structured data with unstructured text and complicate test isolation.

### D3 — `run_id` = `YYYYMMDD_HHMMSS` timestamp string

Simple, human-readable, sortable, unique enough for single-machine use. Included in every event record and also embedded in the log filename, making it easy to correlate filename → events.

### D4 — `stages` dict in `lead` events

Each lead event carries a `stages` sub-object with boolean/value fields per stage that was attempted:
```json
"stages": {
  "website_fetched": true,
  "audit_run": true,
  "json_ld_found": true,
  "instagram_handle_found": false,
  "contact_discovery_run": true,
  "emails_found": 2,
  "social_links_found": 3
}
```
This is the primary tool for understanding enrichment coverage without re-running the pipeline.

### D5 — Per-stage timing via `time.monotonic()` snapshots

Per-lead total duration is measured with `time.monotonic()` diff around the lead processing block. Per-query duration is measured around the Overpass/GooglePlaces call. We do NOT measure every micro-stage individually (too noisy, too many checkpoints) — only query-level and lead-level granularity.

### D6 — `analyze_log.py` reads all JSONL files or a specific one

```
python analyze_log.py                      # analyzes most recent log in logs/
python analyze_log.py logs/pipeline_X.jsonl
```

Outputs sections: Run Summary, Query Coverage, Slowest Queries, Website Status Breakdown, Stage Coverage, Error/Skip Summary.

## Risks / Trade-offs

- [Disk I/O on every lead] → Each `log_lead()` call does one `file.write()` + `file.flush()`. At ~4000 leads × ~500 bytes = ~2MB total, negligible. Flush ensures data is safe if process is killed mid-run.
- [run_europe_smb.py divergence] → This file has its own loop with different variable names. Integration requires parallel changes to keep it consistent with `src/pipeline.py`. Risk: one entry point gets updated, the other is missed. Mitigation: both are covered in the same task group.
- [Log file grows unbounded over many runs] → Out of scope; logs are small (~2–5MB per full run) and the `logs/` directory is clearly named.
