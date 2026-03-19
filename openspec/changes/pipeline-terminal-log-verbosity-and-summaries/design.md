## Context

The project now has human-readable terminal transcripts for pipeline runs, but the first real long-run transcript exposed a mismatch between operator needs and current logging granularity. The run showed useful run/query/batch information, but most of the output volume came from per-lead stage messages, which makes it harder to notice throttling patterns, slow queries, zero-result areas, and final dedup effects while the run is still in progress.

This change is cross-cutting because it affects shared terminal logging conventions, both runtime entry points, runtime configuration, and the testing/documentation surface for operator workflows.

## Goals / Non-Goals

**Goals:**
- Make the default terminal experience concise enough for live monitoring of long runs.
- Preserve access to detailed per-lead tracing through an explicit verbosity setting instead of making it the default for everyone.
- Add query, city, and final summaries that help operators diagnose upstream throttling, sparse markets, and overall lead quality without reading JSONL.
- Keep message formats shared across `src/main.py` and `run_europe_smb.py`.
- Make deduplication outcomes more explainable in the terminal transcript.

**Non-Goals:**
- Replacing the structured JSONL event log or the existing analyzer.
- Building an interactive TUI, progress bar, or dashboard.
- Capturing every low-level HTTP event in the default terminal transcript.
- Changing lead scoring, collection logic, or deduplication algorithms themselves.

## Decisions

### D1 - Introduce explicit terminal verbosity profiles

Use named verbosity profiles such as `normal`, `verbose`, and `debug`.

- `normal`: operator-first output, hiding routine per-lead stage traces and emphasizing run/query/batch/anomaly summaries
- `verbose`: current-style detailed lead stage logging for manual debugging
- `debug`: reserved for even more diagnostic source/retry detail if needed

Chosen over a growing set of boolean logging flags because named modes are easier to document, test, and reason about across entry points.

### D2 - Treat query outcomes as classified states, not only raw durations

Extend terminal query completion messages and summary accounting with derived states such as:

- success with results
- success with zero results
- success after retries
- upstream timeout exhaustion
- rate-limit pressure

Chosen over relying on raw warning lines plus final durations, because operators need a quick answer to "is this market empty or is the upstream unhealthy?"

### D3 - Add rolling summaries at operator-relevant boundaries

Emit summaries at three levels:

- periodic health snapshots during long runs
- city completion summaries after all niches for a city finish
- final operational summary before export completion

Chosen over only a final footer because long runs need mid-run visibility, and chosen over per-query-only logging because operators also need aggregation.

### D4 - Keep detailed tracing possible without making it the default

The terminal transcript should remain a faithful record of what the operator saw, but the default transcript should optimize for readability. Detailed lead-stage output remains available through higher verbosity modes.

Chosen over splitting into separate default and verbose transcript files, which would complicate correlation and operator expectations in the first implementation.

### D5 - Surface deduplication as an explained outcome

Deduplication terminal output should include not only before/after counts but also removed count and a small sample of reasons or signals used to collapse duplicates.

Chosen over leaving dedup as a pure count delta, because repeated brand names in the transcript can otherwise look like logging mistakes or false positives.

## Risks / Trade-offs

- [Operators lose detail they currently rely on] -> Mitigation: preserve `verbose` mode and document when to switch to it.
- [Too many summary lines still create clutter] -> Mitigation: bound periodic summaries to meaningful checkpoints such as every N queries or end-of-city.
- [Shared logging logic becomes stateful and harder to test] -> Mitigation: keep accumulation logic in the shared terminal logging module with focused transcript tests.
- [Dedup reason reporting leaks too much implementation detail] -> Mitigation: keep terminal reasons human-readable and high-level instead of mirroring internal algorithm structures.

## Migration Plan

1. Add verbosity-aware shared logging primitives and summary state tracking in the terminal logging module.
2. Wire verbosity settings into both entry points and pipeline execution paths.
3. Replace unconditional per-lead stage output with verbosity-gated output plus anomaly-safe messages.
4. Add rolling summaries, classified query outcomes, and richer dedup output.
5. Extend transcript tests and update README examples/documentation.

## Open Questions

- Should `normal` mode still emit one final per-lead line for every lead, or should it suppress routine lead output entirely except anomalies?
- Should periodic summaries trigger every fixed number of queries, only at city boundaries, or both?
- Should `debug` mode be fully implemented in this change, or should the initial version ship only `normal` and `verbose` with a reserved enum slot for `debug`?
