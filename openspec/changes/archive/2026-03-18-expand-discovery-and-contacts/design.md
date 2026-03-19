## Context

The pipeline has two entry points with diverging capabilities:

- **`src/pipeline.py` (`LeadPipeline`)** — the canonical entry, driven by `src/main.py`. Uses Google Places as discovery source. Missing: ContactDiscovery, contactability scoring, SocialCollector for Instagram URL extraction, social discovery, and full CSV output.
- **`run_europe_smb.py`** — a standalone extended runner. Uses OpenStreetMap/Overpass. Has all optional modules wired but behind feature flags that default to `false`. Has its own versions of `_generate_outreach_angle()` and `_generate_short_pitch()` that duplicate logic from `pipeline.py`.

Both converge on the same output models (`BusinessLead`), exporters, and scoring modules.

Key bugs/gaps discovered during codebase inspection:
1. `BusinessLead` has no `instagram_url` field. `CrossSourceMatcher._SOCIAL_ATTR_MAP` maps `"instagram"` → `"instagram_url"`, and `SocialCollector` extracts Instagram URLs — but the field to store them doesn't exist. Instagram URL matching in the matcher silently fails.
2. `ContactDiscovery` uses raw phone strings in `all_phones` without calling `normalizer.normalize_phone()`; duplicate phone numbers in different formats (e.g. `+34911234567` vs `91 123 45 67`) are not caught.
3. `compute_contactability_score()` is fully implemented but `pipeline.py` never calls it; `contactability_score` stays `0.0` for all Google Places leads.
4. `exporter_csv.py` exports 21 fixed columns; `exporter_json.py` exports all 49 `BusinessLead` fields. CSV misses all contact discovery results, social URLs, source attribution, and `contactability_score`.
5. `run_europe_smb.py` assigns social URLs from `SocialCollector` to all platforms except Instagram — the `instagram` key is extracted but never written to any lead field.
6. `scoring_rules.json` documents final score weights (`WP=0.35, IG=0.10`) that diverge from hardcoded values in `final_score.py` (`WP=0.30, IG=0.05`). The config file is only read for `city_attractiveness`; all other values are hardcoded.

## Goals / Non-Goals

**Goals:**
- Fix the `instagram_url` field gap on `BusinessLead` so Instagram URL storage and cross-source matching work correctly.
- Wire `ContactDiscovery` and `compute_contactability_score()` into `LeadPipeline` (`pipeline.py`) so Google Places leads also get contact extraction and contactability scoring.
- Apply E.164 normalization inside `ContactDiscovery` for consistent phone deduplication.
- Wire social discovery (`InstagramDiscoveryCollector`, `FacebookDiscoveryCollector`, `CrossSourceMatcher`) into `LeadPipeline` via a feature flag, consistent with how it works in `run_europe_smb.py`.
- Write `instagram_url` from `SocialCollector` output into the new `BusinessLead.instagram_url` field in `run_europe_smb.py`.
- Extend CSV export to include all contact discovery, social URL, source attribution, and scoring fields.
- Enable `enable_contact_discovery=true` as the default in `run_europe_smb.py` to activate the already-implemented logic.

**Non-Goals:**
- Rewriting or merging the two pipeline entry points into one. Both remain. `pipeline.py` is extended; `run_europe_smb.py` is the extended runner and is fixed/updated in place.
- Adding a database persistence layer for contacts. Contacts remain flat fields on `BusinessLead`.
- Fixing the `scoring_rules.json` weight divergence — this is a documentation consistency issue, not a functional bug affecting lead output.
- Improving scraping reliability for Instagram/Facebook (login-wall avoidance, JavaScript rendering). The existing scraping approach is kept as-is with its known limitations.
- Adding new discovery sources beyond what already exists (no new collectors).
- Refactoring `EnrichedRecord`, `RawBusinessRecord`, or `ContactType`/`ContactCategory` dead code — these are cleanup concerns deferred to a housekeeping change.

## Decisions

### Decision 1: Fix `instagram_url` by adding it as an explicit field on `BusinessLead`

**Options considered:**
- A) Add `instagram_url: Optional[str] = None` field to `BusinessLead` alongside the other 8 social URL fields.
- B) Rename `SocialCollector` output mapping key to write Instagram URL into an existing field (e.g., reuse `facebook_url` naming pattern).
- C) Store Instagram URL only in `social_urls` dict, not as a flat field.

**Decision: Option A.** `BusinessLead` already has flat fields for 8 other social platforms (`facebook_url`, `twitter_url`, `tiktok_url`, `linkedin_url`, `youtube_url`, `pinterest_url`, `whatsapp_url`, `telegram_url`). Instagram is clearly a first-class signal in this system — the `InstagramStatus` enum, `instagram_signal_score`, and `InstagramSignalCollector` all exist. Adding `instagram_url` completes the pattern. `CrossSourceMatcher._SOCIAL_ATTR_MAP` already maps to `"instagram_url"` — the model just needs to catch up.

### Decision 2: Wire `ContactDiscovery` into `LeadPipeline` behind an existing-style feature flag

**Options considered:**
- A) Make `ContactDiscovery` always active in `LeadPipeline` (no flag).
- B) Add `enable_contact_discovery` flag to `LeadPipeline`'s `InputConfig`, matching how `run_europe_smb.py` works.
- C) Keep it out of `LeadPipeline`; only available in `run_europe_smb.py`.

**Decision: Option B.** Consistency with the existing pattern in `run_europe_smb.py`. The `InputConfig` Pydantic model already defines feature flags; adding `enable_contact_discovery` with a default of `true` is minimal and clear. Users who don't want the extra HTTP requests (contact sub-page fetch) can disable it.

### Decision 3: Apply E.164 normalization inside `ContactDiscovery` using the existing `normalizer.normalize_phone()`

**Options considered:**
- A) Apply normalization in `ContactDiscovery._clean_phone()`, calling `normalizer.normalize_phone()`.
- B) Apply normalization in `ContactDiscovery.apply_to_lead()` before writing to the lead.
- C) Leave phone normalization to the deduplicator (which already does it for `place_id` / `text search` phone field).

**Decision: Option A.** Normalization should happen at the point of ingestion, not downstream. `_clean_phone()` is the designated phone-cleaning hook. Calling `normalize_phone()` there keeps the logic close to extraction and ensures `all_phones` always contains canonical E.164 strings.

### Decision 4: Extend CSV to all 49 fields, preserving existing 21-column order

**Options considered:**
- A) Replace the 21-column `COLUMNS` list with the full 49-field schema.
- B) Add an opt-in `--extended` flag to the CSV exporter that appends extra columns.
- C) Keep the 21-column CSV as default; add a separate `_extended.csv` output.

**Decision: Option A.** The JSON exporter already exports all 49 fields. Having the CSV be a subset without a prominent warning means any consumer using CSV gets an incomplete view silently. Adding the missing columns is additive and backward-compatible for row ordering (new columns append after the existing 21). Existing column order is preserved.

### Decision 5: Default `enable_contact_discovery=true` in `run_europe_smb.py` config

**Options considered:**
- A) Change the default in the config loader so runs use contact discovery unless explicitly disabled.
- B) Keep `false` as default; document it better.
- C) Read the default from `config/run_europe_smb.json`.

**Decision: Option A.** `ContactDiscovery` is fully implemented, tested, and already wired in the runner. The only reason it defaults to `false` is that it was added incrementally. Since the stated goal is maximum contact data collection and the module works, the default should reflect that. The feature flag remains available for disabling.

## Risks / Trade-offs

- **Instagram/Facebook scraping reliability** — both collectors return very limited data when platforms return login walls. No mitigation in this change; accepted limitation, callers handle empty `SocialCandidate` lists gracefully.
- **ContactDiscovery extra HTTP request** — each lead with a website may trigger one additional HTTP request to a `/contact` sub-page. This increases run time proportionally to lead count. Mitigation: this is already gated by `enable_contact_discovery` flag.
- **CSV column expansion** — any downstream tool that reads the CSV by column index (not header name) will break. Mitigation: downstream tools should use header-based column parsing; this is documented in the export spec as a requirement.
- **E.164 normalization requires `phonenumbers` package** — already in `requirements.txt`. Graceful fallback: if `normalize_phone()` fails (unparseable number or missing region), `_clean_phone()` falls back to returning the raw string (existing behavior).
- **`instagram_url` is a new JSON field** — additive to the schema. Any JSON consumer that deserializes to a strict typed model may need updating. Mitigation: field is `Optional[str]` defaulting to `None`, so it serializes as `null` and won't break existing JSON parsers that ignore unknown/null fields.

## Migration Plan

1. Apply model change (`instagram_url` field on `BusinessLead`) — no migration needed, field is `None` by default.
2. Apply `ContactDiscovery` phone normalization — no data migration; affects future runs only.
3. Wire `ContactDiscovery` + contactability scoring into `LeadPipeline` — guarded by flag; existing runs using `src/main.py` with no flag change are unaffected.
4. Update `run_europe_smb.py` to assign `instagram_url` and default `enable_contact_discovery=true` — first run after change will produce richer outputs.
5. Extend CSV — any previously generated CSV files are unaffected; new runs produce wider CSVs.
6. No database migrations, no API changes, no deployment steps.

**Rollback**: All changes are reversible — field default is `None`, flag default reverts, CSV column list reverts. No destructive operations.

## Open Questions

- Should `scoring_rules.json` weights be enforced at runtime instead of hardcoded? — Out of scope for this change; flagged as tech debt.
- Should `pipeline.py` and `run_europe_smb.py` eventually be unified into a single configurable runner? — Out of scope; would require a larger architectural change.
- Should `linkedin_url`, `youtube_url`, and similar rarely-populated fields be de-prioritised in CSV output? — No; include all fields for completeness per Decision 4.
