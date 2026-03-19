## 1. Fix BusinessLead model

- [x] 1.1 Add `instagram_url: Optional[str] = None` field to `BusinessLead` in `src/models.py`, positioned after `telegram_url` to complete the social URL field group
- [x] 1.2 Add `instagram_url` to `BusinessLead.to_json()` output dict (alongside other social URL fields)
- [x] 1.3 Verify `CrossSourceMatcher._SOCIAL_ATTR_MAP["instagram"] == "instagram_url"` now maps to a real field (no code change needed — fix is in the model)

## 2. Fix instagram_url assignment in run_europe_smb.py

- [x] 2.1 In `run_europe_smb.py`, locate the block that assigns social URLs from `SocialCollector` output to lead fields; add `lead.instagram_url = social.get("instagram")` alongside the existing assignments for `facebook_url`, `twitter_url`, etc.
- [x] 2.2 Verify the assignment only writes when the value is non-null (use `or` guard or explicit `if` check, consistent with surrounding code style)

## 3. Apply E.164 phone normalization inside ContactDiscovery

- [x] 3.1 In `src/enrichment/contact_discovery.py`, import `normalize_phone` from `src.enrichment.normalizer`
- [x] 3.2 In `ContactDiscovery._clean_phone()`, call `normalize_phone(raw, default_region)` before returning; fall back to the raw string if normalization raises or returns `None`
- [x] 3.3 Pass the business country code (derived from `lead.country` or config) as `default_region` to `normalize_phone()` so local-format numbers without country prefix can be resolved
- [x] 3.4 Run existing tests (e.g. `tests/test_normalizer.py`) to confirm no regressions

## 4. Wire ContactDiscovery into LeadPipeline

- [x] 4.1 Add `enable_contact_discovery: bool = True` to `InputConfig` in `src/models.py` (alongside existing feature flags, defaulting to `True`)
- [x] 4.2 In `src/pipeline.py`, import `ContactDiscovery` from `src.enrichment.contact_discovery`
- [x] 4.3 In `LeadPipeline.__init__()`, instantiate `self._contact_discovery = ContactDiscovery()` if `enable_contact_discovery` is `True`
- [x] 4.4 In `LeadPipeline.run()`, after the website check and audit step, call `ContactDiscovery.extract(lead, response)` and `ContactDiscovery.apply_to_lead(lead, result)` for each lead where `website_status == HAS_WEBSITE` and `enable_contact_discovery` is `True`
- [x] 4.5 Guard the ContactDiscovery call with a try/except so a single-lead failure does not abort the entire pipeline run

## 5. Wire contactability scoring into LeadPipeline

- [x] 5.1 In `src/pipeline.py`, import `compute_contactability_score` from `src.scoring.contactability`
- [x] 5.2 In the scoring stage of `LeadPipeline.run()`, call `compute_contactability_score(lead)` and store the result in `lead.contactability_score`
- [x] 5.3 Pass the computed `contactability_score` as the `contactability` argument to `compute_final_score()` (currently hardcoded `0.0`)
- [x] 5.4 Confirm `lead.contactability_score` and the updated `lead_priority_score` appear in JSON output after this change

## 6. Wire social discovery into LeadPipeline

- [x] 6.1 Add `enable_social_discovery: bool = False` to `InputConfig` in `src/models.py` (default `False` to maintain backward compatibility for `src/main.py` users who have no social API credentials)
- [x] 6.2 In `src/pipeline.py`, import `InstagramDiscoveryCollector`, `FacebookDiscoveryCollector`, and `CrossSourceMatcher`
- [x] 6.3 After the main Google Places discovery + scoring loop in `LeadPipeline.run()`, add a social discovery block (guarded by `enable_social_discovery`) that mirrors the logic in `run_europe_smb.py`: run collectors per niche × city, match candidates, merge or promote stubs
- [x] 6.4 Ensure stub leads created from unmatched social candidates have `lead.instagram_url` populated from `candidate.social_urls.get("instagram")` where applicable
- [x] 6.5 Confirm social discovery block does not run when `enable_social_discovery=False` (no imports of discovery collectors executed if flag is False)

## 7. Set enable_contact_discovery=True as default in run_europe_smb.py

- [x] 7.1 In `run_europe_smb.py` (or its config loader), change the default value of `enable_contact_discovery` from `False` to `True`
- [x] 7.2 Verify the config file `config/run_europe_smb.json` does not explicitly override `enable_contact_discovery` to `False` (check and update if so)
- [x] 7.3 Confirm that a test run with `enable_contact_discovery=True` does not raise errors on leads without websites (ContactDiscovery should skip or handle gracefully)

## 8. Extend CSV export

- [x] 8.1 In `src/output/exporter_csv.py`, replace the 21-item `COLUMNS` list with the full `BusinessLead` field schema (49 fields), preserving existing columns in their current order and appending new columns after them
- [x] 8.2 Add serialisation logic for list fields (`all_emails`, `all_phones`, `whatsapp_links`, `messenger_links`, `booking_links`, `contact_form_urls`, `source_platforms`, `issues_found`, `improvement_opportunities`) using `|` as separator (matching the existing pattern for `issues_found`)
- [x] 8.3 Add `instagram_url` to the new CSV column list immediately after `telegram_url` (consistent with model field order)
- [x] 8.4 Verify `contactability_score` appears as a column in the CSV output
- [x] 8.5 Run `tests/test_pipeline_smoke.py` (or equivalent) and confirm the CSV output file can be read without error and contains expected column headers

## 9. Validation and smoke testing

- [x] 9.1 Run `python _smoke_tests.py` and confirm no failures
- [x] 9.2 Run `python -m pytest tests/ -x -q` and confirm all existing tests pass
- [x] 9.3 Run a minimal dry-run of `src/main.py` with a test config (1 city, 1 niche, max 3 results) and inspect the JSON output — verify `instagram_url`, `contactability_score`, and `primary_email` are present
- [x] 9.4 Run a minimal dry-run of `run_europe_smb.py` with `enable_contact_discovery=true` and `enable_social_discovery=false` — confirm no regressions in scoring and export
- [x] 9.5 Inspect generated CSV and confirm it contains all expected columns including the newly added contact and social fields
