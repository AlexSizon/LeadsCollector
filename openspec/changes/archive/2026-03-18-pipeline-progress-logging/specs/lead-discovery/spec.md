## ADDED Requirements

### Requirement: Lead discovery pipeline emits structured log events per query
The lead discovery stage SHALL, when a `PipelineLogger` is active, emit one `query` log event per niche × city combination, capturing the data source used, result count, and wall-clock duration of the search call. This applies to both `src/pipeline.py` (LeadPipeline) and `run_europe_smb.py`.

#### Scenario: Query event emitted after successful Overpass search in LeadPipeline
- **WHEN** `LeadPipeline.run()` completes an Overpass search for a niche × city combination
- **THEN** a `query` event SHALL be written to the active `PipelineLogger` with `source="overpass"`, `city`, `niche`, `result_count`, and `duration_s`

#### Scenario: Query event emitted after GooglePlaces fallback failure
- **WHEN** GooglePlaces raises an exception and Overpass is used as fallback in `LeadPipeline.run()`
- **THEN** the `query` event SHALL have `source="overpass"` and SHALL also include `fallback=true`

#### Scenario: Query event emitted in run_europe_smb.py
- **WHEN** `run_europe_smb.py` completes an Overpass search for a niche × city combination
- **THEN** a `query` event SHALL be emitted to the same `PipelineLogger` instance used for the run
