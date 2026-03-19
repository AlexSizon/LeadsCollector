## 1. Shared Terminal Logging Utility

- [x] 1.1 Add a shared terminal logging module that creates a per-run transcript file using the pipeline `run_id`
- [x] 1.2 Implement logger/handler setup that writes the same human-readable messages to stdout and the transcript file without duplicating handlers
- [x] 1.3 Add helper functions or conventions for consistent step-level terminal messages (run start, query progress, lead progress, deduplication, export)

## 2. Main Pipeline Integration

- [x] 2.1 Wire terminal transcript setup into the `src/main.py` execution path and surface the transcript location at run start
- [x] 2.2 Update `src/pipeline.py` to emit shared terminal progress messages for query start/completion, fallback/error state, and major enrichment/scoring checkpoints
- [x] 2.3 Add terminal summary messages for deduplication completion and final lead counts in the main pipeline path
- [x] 2.4 Ensure the main pipeline path flushes and closes the terminal transcript cleanly on success and failure

## 3. OSM Runner Integration

- [x] 3.1 Replace the standalone terminal logging setup in `run_europe_smb.py` with the shared terminal logging utility
- [x] 3.2 Align `run_europe_smb.py` terminal messages with the shared step vocabulary used by the main pipeline path
- [x] 3.3 Add terminal summary messages for export outputs and transcript location in the OSM runner
- [x] 3.4 Ensure the OSM runner closes the terminal transcript cleanly even when a run exits with errors

## 4. Validation And Documentation

- [x] 4.1 Add tests for transcript file creation and shared terminal logging output formatting
- [x] 4.2 Add or extend smoke tests to verify major pipeline step messages are emitted and persisted for at least one run path
- [x] 4.3 Document the new terminal transcript behavior and file location in `README.md`
- [x] 4.4 Run targeted validation to confirm a pipeline run produces both structured JSONL logs and a human-readable terminal transcript
