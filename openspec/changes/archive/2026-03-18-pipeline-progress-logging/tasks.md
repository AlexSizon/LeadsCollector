## 1. PipelineLogger utility

- [x] 1.1 Create `src/logging_utils.py` with a `PipelineLogger` class: `__init__(run_id: str, log_dir: Path)` — creates `log_dir` if missing, opens `log_dir/pipeline_<run_id>.jsonl` in append mode
- [x] 1.2 Add `_write(event: dict)` private method: serialises to JSON, appends `\n`, calls `flush()`
- [x] 1.3 Add `log_run_start(config: dict)` method: writes `event="run_start"` with `run_id`, `ts`, `config_cities`, `config_niches`, `config_countries`, `max_results_per_query`
- [x] 1.4 Add `log_run_end(total_leads: int, duration_s: float)` method: writes `event="run_end"` with `run_id`, `ts`, `total_leads`, `duration_s`
- [x] 1.5 Add `log_query(city: str, niche: str, source: str, result_count: int, duration_s: float, *, fallback: bool = False, error: Optional[str] = None)` method: writes `event="query"` with all fields
- [x] 1.6 Add `log_lead(lead: BusinessLead, stages: dict, duration_s: float)` method: writes `event="lead"` with `run_id`, `ts`, `company`, `city`, `niche`, `website_status`, `score`, `tier`, `duration_s`, `stages`
- [x] 1.7 Add `close()` method that closes the file handle; add `__enter__`/`__exit__` for context-manager support
- [x] 1.8 Add `generate_run_id()` module-level helper: returns `datetime.utcnow().strftime("%Y%m%d_%H%M%S")`

## 2. Integrate PipelineLogger into src/pipeline.py

- [x] 2.1 Import `PipelineLogger` and `generate_run_id` in `src/pipeline.py`
- [x] 2.2 In `LeadPipeline.__init__()`: call `generate_run_id()`, instantiate `PipelineLogger`, store as `self._logger`; use `LOG_DIR = Path(__file__).parent.parent / "logs"`
- [x] 2.3 In `LeadPipeline.run()`: call `self._logger.log_run_start(config)` at the start, wrap the body in try/finally to guarantee `log_run_end` is always called
- [x] 2.4 In the per-query loop: record `_q_start = time.monotonic()` before the GooglePlaces/Overpass call, call `self._logger.log_query(...)` after `places` is assigned, passing `source="google_places"` or `"overpass"`, `result_count=len(places)`, `duration_s`, `fallback=_source_is_osm`
- [x] 2.5 In the per-lead loop: record `_lead_start = time.monotonic()` before lead creation, build the `stages` dict after scoring (containing `website_fetched`, `audit_run`, `json_ld_found`, `emails_found`, `social_links_found`, `instagram_handle_found`, `contact_discovery_run`)
- [x] 2.6 Call `self._logger.log_lead(lead, stages, duration_s)` immediately before `leads.append(lead)`
- [x] 2.7 In `log_run_end` call (in the finally block): pass `total_leads=len(leads)` and wall-clock `duration_s` since `run()` started

## 3. Integrate PipelineLogger into run_europe_smb.py

- [x] 3.1 Import `PipelineLogger`, `generate_run_id` from `src.logging_utils` in `run_europe_smb.py`; instantiate logger at the top of `run_pipeline()` using `LOG_DIR = ROOT / "logs"`
- [x] 3.2 Call `logger.log_run_start(config)` at the start of `run_pipeline()`
- [x] 3.3 In the per-query loop: same pattern as 2.4 — wrap the `collector.search()` call, emit `log_query()` after
- [x] 3.4 In the per-lead loop: record `_lead_start`, build stages dict, call `logger.log_lead()` before appending
- [x] 3.5 Wrap `run_pipeline()` body in try/finally; call `logger.log_run_end(len(leads), duration_s)` in finally
- [x] 3.6 Call `logger.close()` in the finally block

## 4. analyze_log.py CLI tool

- [x] 4.1 Create `analyze_log.py` at project root; parse optional positional argument (log file path); if absent, find the most recent `logs/pipeline_*.jsonl` by sorted filename; exit with error if none found
- [x] 4.2 Load all lines from the log file into a list of event dicts (skip malformed lines with a warning)
- [x] 4.3 Implement `print_run_summary(events)`: extract `run_start`/`run_end` events, print run_id, start time, duration, total leads, city and niche counts
- [x] 4.4 Implement `print_query_coverage(events)`: collect all `query` events, print zero-result queries table and top-10 slowest queries table (sorted by `duration_s` desc)
- [x] 4.5 Implement `print_stage_coverage(events)`: collect all `lead` events, print website status breakdown (counts + %) and per-stage coverage rates (`emails_found > 0`, `json_ld_found`, `instagram_handle_found`, `contact_discovery_run`)
- [x] 4.6 Implement `print_score_distribution(events)`: print tier distribution (count per tier) and average score per city (sorted desc by avg score)
- [x] 4.7 Wire all four print functions into a `main()` function called from `if __name__ == "__main__"`

## 5. Tests

- [x] 5.1 Add `tests/test_pipeline_logger.py`: test `log_run_start` writes valid JSON with correct fields; test `log_query` writes correct `event="query"` line; test `log_lead` writes correct `event="lead"` line with nested `stages`; test `close()` flushes and closes file
- [x] 5.2 Test that `PipelineLogger` context manager (`with PipelineLogger(...) as logger`) calls `close()` on exit
- [x] 5.3 Test `generate_run_id()` returns a string matching `r"\d{8}_\d{6}"`
- [x] 5.4 Add a smoke test in `tests/test_pipeline_smoke.py` that runs a minimal pipeline (mocked collectors) and asserts that `logs/` receives a JSONL file containing at least `run_start` and `run_end` events

## 6. Validation

- [x] 6.1 Run `python -m pytest tests/ -v` — all existing 198 tests must pass without modification
- [x] 6.2 Run a minimal test run (`python -m src.main --config config/test_run.json ...`) and verify a JSONL log file is created in `logs/` with valid JSON on each line
- [x] 6.3 Run `python analyze_log.py` against the test run log and verify all four sections are printed without error
