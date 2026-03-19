## Why

All the modules needed for full contact and social-discovery enrichment already exist in the codebase, but they are either silently broken (missing `instagram_url` field on `BusinessLead` breaks Instagram cross-source matching), wired only to the secondary entry point (`run_europe_smb.py`) behind flags that default to `false`, or completely absent from the primary pipeline (`src/pipeline.py`). The result is that the canonical pipeline outputs zero contactability scores, drops social URLs, omits ~25 fields from CSV exports, and can never match Instagram leads — even though all the code to do these things is written and tested.

## What Changes

- **Add `instagram_url` field to `BusinessLead`** — currently `CrossSourceMatcher` and `SocialCollector` both reference this field but it doesn't exist on the model, causing silent attribute errors and broken Instagram URL matching.
- **Wire `ContactDiscovery` into both pipeline entry points** — `contact_discovery.py` is fully implemented but only called in `run_europe_smb.py` behind `enable_contact_discovery=false`.
- **Wire `compute_contactability_score()` everywhere** — the function is implemented but `pipeline.py` never calls it; `contactability_score` remains `0.0` for all Google Places leads.
- **Apply E.164 phone normalization inside `ContactDiscovery`** — `normalizer.py` already has `normalize_phone()` but `contact_discovery.py` doesn't use it; `all_phones` contains raw strings that can't deduplicate across formats.
- **Enable social discovery and cross-source matching in the primary pipeline** — `InstagramDiscoveryCollector`, `FacebookDiscoveryCollector`, and `CrossSourceMatcher` exist but are absent from `LeadPipeline` in `pipeline.py`.
- **Extend CSV export to include all contact and source fields** — `exporter_csv.py` has 21 columns; `exporter_json.py` exports all 49 fields including all contact/social/source attribution; CSV must be brought to parity.
- **Stop silently dropping Instagram URL from `SocialCollector` output** — `run_europe_smb.py` assigns all 8 social platforms except Instagram to lead fields; Instagram URL is extracted but never stored.
- **Activate social-first lead preservation by default** — unmatched social candidates should be saved as stub leads rather than discarded; the logic exists but the flag defaults to `false`.

## Capabilities

### New Capabilities

- `export-format`: Defines the canonical output field contract for both JSON and CSV exports, covering all 49 `BusinessLead` fields including contact discovery, social URLs, source attribution, and all scoring dimensions.

### Modified Capabilities

- `lead-discovery`: Add `instagram_url` to the `BusinessLead` output schema; unify both pipeline entry points to include social discovery, contact discovery, and contactability scoring; preserve social-first leads.
- `contact-discovery`: Require E.164 phone normalization for all extracted phone values; require the module to be active by default (no longer opt-in flag); fix `all_phones` deduplication to handle cross-format equivalence.
- `lead-scoring`: Require that `contactability_score` is always computed and passed to `compute_final_score()` in both entry points, not defaulted to `0.0`.
- `social-discovery`: Fix `instagram_url` field reference so Instagram URL matching in `CrossSourceMatcher` fires correctly; require social discovery to run and integrate with the primary pipeline.

## Impact

- **Files modified**: `src/models.py` (add `instagram_url` field), `src/pipeline.py` (wire ContactDiscovery, contactability scoring, social discovery), `src/enrichment/contact_discovery.py` (E.164 phone normalization), `src/enrichment/cross_source_matcher.py` (no change — bug resolved by fixing model), `src/output/exporter_csv.py` (extend to 49 columns), `run_europe_smb.py` (assign `instagram_url` from SocialCollector, default `enable_contact_discovery=true`)
- **No new dependencies** — all required packages (`phonenumbers`, `dnspython`, etc.) already declared in `requirements.txt`
- **No DB layer changes** — contacts remain flat fields on `BusinessLead`; no persistence layer exists to migrate
- **Backward-compatible** — JSON output schema is additive (new `instagram_url` field); CSV column additions are append-only; existing config files continue to work; `enable_social_discovery` flag still respected if explicitly set to `false`
