## Context

The project now has structured JSONL telemetry for pipeline runs, but live runtime feedback is still fragmented. `run_europe_smb.py` emits some ad hoc `log.info(...)` lines, while `src/pipeline.py` mostly relies on silent work plus the file logger. Operators running long scans need two things at the same time:

- clear terminal progress for each major pipeline step
- a persisted human-readable terminal transcript they can review after the run

This change is cross-cutting because it affects both pipeline entry points, shared logging behavior, output conventions, and operator-facing runtime messaging.

## Goals / Non-Goals

**Goals:**
- Persist terminal stdout/stderr to a per-run log file with the same run identity used by structured logging.
- Emit consistent terminal messages for major steps such as run start, query execution, lead enrichment progress, deduplication, and export completion.
- Reuse a shared implementation so `src/main.py` + `src/pipeline.py` and `run_europe_smb.py` behave consistently.
- Keep terminal output readable during long runs by favoring concise stage summaries over raw debug noise.

**Non-Goals:**
- Replacing the structured JSONL event log.
- Building a rich TUI/progress-bar interface.
- Logging every micro-action for every field extracted from every lead.
- Introducing remote log shipping or centralized observability tooling.

## Decisions

### D1 — Introduce a shared terminal logging utility

Add a small shared utility module responsible for:
- creating a timestamped terminal log file per run
- wiring Python logging to both stdout and the terminal log file
- formatting stage messages consistently

Chosen over:
- duplicating `logging.basicConfig(...)` changes in multiple entry points
- redirecting shell output externally with `tee`, which would not standardize application-generated step messages

### D2 — Use the existing `run_id` as the terminal-log correlation key

Terminal transcript files should use the same run identity as the JSONL logs so operators can correlate:
- structured JSONL events
- human-readable terminal output
- exported JSON/CSV artifacts

Chosen over separate terminal-only timestamps, which would make post-run correlation harder.

### D3 — Log major pipeline stages, not every internal branch

Terminal logging should cover the operator-relevant checkpoints:
- run initialization
- per-query start/completion and fallback/error state
- per-lead stage progression at a summarized level
- deduplication start/end
- export start/end

Chosen over exhaustive per-function tracing, which would produce too much noise for 4–8 hour runs.

### D4 — Keep stdout and file transcript content aligned

The persisted terminal log should mirror what the operator sees in the terminal, rather than becoming a second structured log format. The JSONL logger remains the machine-readable source of truth; terminal logs remain narrative and operational.

Chosen over emitting a second JSON/CSV runtime stream, which would duplicate the purpose of `pipeline_<run_id>.jsonl`.

## Risks / Trade-offs

- [Too much terminal noise] → Mitigation: define a limited vocabulary of stage-level messages and avoid verbose per-field diagnostics by default.
- [Divergence between entry points] → Mitigation: centralize terminal-log setup and message helpers in shared code rather than hand-maintaining two formats.
- [Extra file I/O] → Mitigation: terminal transcripts are append-only text and small relative to runtime; this is acceptable for operational visibility.
- [User confusion between terminal log and JSONL log] → Mitigation: use clear filenames and message text that distinguishes human-readable terminal transcripts from structured event logs.

## Migration Plan

1. Add the shared terminal logging utility and wire it into both entry points.
2. Introduce stage-level terminal messages in discovery, enrichment, deduplication, and export paths.
3. Validate that each run produces both a structured JSONL file and a readable terminal transcript.
4. Document the new terminal log location and intended usage in README or operator docs.

## Open Questions

- Whether per-lead terminal messages should be emitted for every lead or only at interval-based checkpoints when runs become large.
- Whether transcript files should live directly under `logs/` or under a dedicated subdirectory such as `logs/terminal/`.
