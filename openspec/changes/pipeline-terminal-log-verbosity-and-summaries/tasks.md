## 1. Shared Logging Controls

- [x] 1.1 Add a shared terminal verbosity model and configuration plumbing in the terminal logging module
- [x] 1.2 Implement verbosity-aware helpers so normal mode suppresses routine per-lead stage lines while verbose mode preserves detailed tracing
- [x] 1.3 Add anomaly-visible message helpers for zero-result queries, upstream failures, and unexpected website outcomes

## 2. Query And Summary Instrumentation

- [x] 2.1 Extend query terminal messages with classified status and retry-count fields
- [x] 2.2 Add rolling summary state tracking for warnings, zero-result queries, slow queries, and website-status distribution
- [x] 2.3 Emit city-level completion summaries and periodic health snapshots from shared logging code
- [x] 2.4 Emit richer final run summaries before export completion, including slow-query and warning totals

## 3. Dedup And Entry Point Integration

- [x] 3.1 Add deduplication explainability output with removed-count and sample reason details
- [x] 3.2 Wire terminal verbosity selection through `src/main.py` and `src/pipeline.py`
- [x] 3.3 Wire the same terminal verbosity and summary behavior through `run_europe_smb.py`
- [x] 3.4 Ensure both entry points keep shared formatting and anomaly behavior in normal and verbose modes

## 4. Validation And Documentation

- [x] 4.1 Add transcript tests for normal versus verbose logging behavior
- [x] 4.2 Add tests for summary emission, query status classification, and dedup explainability
- [x] 4.3 Update `README.md` with verbosity modes, summary behavior, and operator guidance
- [x] 4.4 Run targeted validation on a long-run config to confirm concise mode remains readable while preserving key anomalies and summaries
