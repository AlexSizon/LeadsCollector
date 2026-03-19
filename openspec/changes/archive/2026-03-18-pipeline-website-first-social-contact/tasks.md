## 1. Model and Enum Extensions

- [x] 1.1 Add `SocialPresenceStatus` string enum to `src/enums.py` (values: `FOUND_ON_WEBSITE`, `FOUND_IN_SCHEMA`, `FOUND_VIA_HUB`, `FOUND_VIA_SEARCH`, `NOT_FOUND`, `UNKNOWN`)
- [x] 1.2 Add `instagram_presence_status: SocialPresenceStatus` field to `BusinessLead` dataclass in `src/models.py` (default: `SocialPresenceStatus.UNKNOWN`)
- [x] 1.3 Add `facebook_presence_status: SocialPresenceStatus` field to `BusinessLead` dataclass in `src/models.py` (default: `SocialPresenceStatus.UNKNOWN`)
- [x] 1.4 Add `social_discovery_method: Optional[str]` field to `BusinessLead` dataclass in `src/models.py` (default: `None`)
- [x] 1.5 Add the three new fields to `BusinessLead.to_json()` — `instagram_presence_status` and `facebook_presence_status` as `.value` strings, `social_discovery_method` as-is

## 2. JSON-LD Extractor Module

- [x] 2.1 Create `src/enrichment/json_ld_extractor.py` with `extract_from_html(html: str) -> dict` function
- [x] 2.2 Implement scanning all `<script type="application/ld+json">` elements using BeautifulSoup
- [x] 2.3 Implement entity type scoring: prefer specific LocalBusiness subtypes over generic `Organization`/`WebSite`
- [x] 2.4 Implement extraction of `telephone`, `email`, `name`, `address` (structured PostalAddress), `openingHours`, `sameAs` array
- [x] 2.5 Implement `sameAs` social URL classification: identify instagram.com, facebook.com, twitter.com, linkedin.com, tiktok.com, youtube.com URLs
- [x] 2.6 Handle malformed JSON-LD blocks with try/except — log at debug level and continue
- [x] 2.7 Return empty dict `{}` when no JSON-LD blocks found or no LocalBusiness entity found
- [x] 2.8 Write unit tests for `json_ld_extractor.extract_from_html()` covering: valid entity, malformed JSON, no blocks, sameAs social URLs, multiple blocks (specificity wins)

## 3. SocialCollector Wiring in Stage 3

- [x] 3.1 Import `SocialCollector` in `src/pipeline.py` and instantiate it in `LeadPipeline.__init__()`
- [x] 3.2 In Stage 3 (after website status confirmed as `HAS_WEBSITE`), call `SocialCollector.extract_from_html(html, lead.website_url)` on the cached website response HTML
- [x] 3.3 Apply `SocialCollector` results to lead social URL fields (`instagram_url`, `facebook_url`, `tiktok_url`, `linkedin_url`, `youtube_url`, `pinterest_url`, `whatsapp_url`, `telegram_url`) using fill-if-empty semantics
- [x] 3.4 Set `lead.instagram_presence_status = FOUND_ON_WEBSITE` when `instagram_url` is populated from `SocialCollector`; set `lead.facebook_presence_status = FOUND_ON_WEBSITE` for Facebook
- [x] 3.5 Set `lead.social_discovery_method = "website_html"` when any social URL is newly set from `SocialCollector`
- [x] 3.6 Retire the `InstagramSignalCollector.extract_handle_from_html()` call — pass the handle already obtained from `SocialCollector`'s `instagram` result to `analyze_handle()` instead (handle may be `None` if not found)
- [x] 3.7 Guard the `InstagramSignalCollector.analyze_handle()` call: only call it if `lead.instagram_url` is non-null; set `lead.instagram_status = InstagramStatus.NOT_FOUND` otherwise

## 4. JSON-LD Extraction Wiring in Stage 3

- [x] 4.1 Import `json_ld_extractor` in `src/pipeline.py`
- [x] 4.2 Call `json_ld_extractor.extract_from_html(response.text)` in Stage 3 after `SocialCollector` extraction, for all leads with `HAS_WEBSITE`
- [x] 4.3 Apply JSON-LD `phone` to `lead.phone` (fill-if-empty, E.164 normalize via `normalize_phone()`)
- [x] 4.4 Apply JSON-LD `email` to `lead.all_emails` (fill-if-empty, deduplicate, lowercase)
- [x] 4.5 Apply JSON-LD `sameAs` Instagram URL: set `lead.instagram_url` (fill-if-empty) and `lead.instagram_presence_status = FOUND_IN_SCHEMA`; set `lead.social_discovery_method = "json_ld"` if not already set to a higher-fidelity value
- [x] 4.6 Apply JSON-LD `sameAs` Facebook URL: set `lead.facebook_url` (fill-if-empty) and `lead.facebook_presence_status = FOUND_IN_SCHEMA`
- [x] 4.7 Apply JSON-LD `sameAs` other social URLs (Twitter, LinkedIn, TikTok) to remaining lead fields (fill-if-empty)

## 5. Linktree / Hub Resolution in Stage 3

- [x] 5.1 Define the hub domain allowlist constant in `pipeline.py` (or a small helper): `LINK_HUB_DOMAINS = {"linktr.ee", "beacons.ai", "bio.site", "solo.to", "taplink.cc"}`
- [x] 5.2 After `SocialCollector` runs, check if any extracted social URL (or the website URL itself) matches a hub domain using `domain_resolver.extract_root_domain()`
- [x] 5.3 If a hub URL is detected and `enable_linktree_resolution` is `true` (config flag, default `true`), make one GET request (timeout ≤ 5s) to the hub URL
- [x] 5.4 On successful hub fetch, run `SocialCollector.extract_from_html(hub_html, hub_url)` on the hub page HTML
- [x] 5.5 Apply hub-sourced social URLs to lead using fill-if-empty semantics; set `instagram_presence_status = FOUND_VIA_HUB` for any Instagram URL newly set; same for Facebook
- [x] 5.6 Set `lead.social_discovery_method = "hub_resolution"` when hub extraction contributes new URLs
- [x] 5.7 Wrap the hub fetch in try/except — log debug warning on failure, continue without raising

## 6. EmailGuesser Wiring

- [x] 6.1 Import `EmailGuesser` in `src/pipeline.py` and instantiate it once in `LeadPipeline.__init__()` (or lazily gate on `enable_email_guesser`)
- [x] 6.2 After `ContactDiscovery.apply_to_lead()` completes in Stage 3c, check if `lead.all_emails` is empty AND `lead.website_url` is non-null AND `enable_email_guesser` is `true` (default `true`)
- [x] 6.3 If conditions met, call `EmailGuesser.guess(lead.website_url, lead.niche)` and write result to `lead.guessed_email`
- [x] 6.4 Wrap `EmailGuesser.guess()` call in try/except — log debug warning on failure, set `lead.guessed_email = None`, continue

## 7. OverpassCollector as Places Fallback

- [x] 7.1 Import `OverpassCollector` in `src/pipeline.py`
- [x] 7.2 Wrap the `GooglePlacesCollector.search()` call in Stage 1 with try/except catching authentication and quota errors
- [x] 7.3 On error, log a warning and fall through to `OverpassCollector.search()` with the same query arguments; tag resulting leads with `lead_source = LeadSourceType.OSM`
- [x] 7.4 Ensure `OverpassCollector.get_place_details()` results are normalized the same way as Google Places results before being passed to Stage 2

## 8. Social Presence Status Final Sweep in Stage 5b

- [x] 8.1 After cross-source matching completes in Stage 5b, for leads that still have `instagram_url=None`, set `lead.instagram_presence_status = SocialPresenceStatus.NOT_FOUND`
- [x] 8.2 For leads that still have `facebook_url=None` after Stage 5b, set `lead.facebook_presence_status = SocialPresenceStatus.NOT_FOUND`
- [x] 8.3 In `CrossSourceMatcher.merge_into()`: when writing a social URL from a search-sourced candidate, set the corresponding presence status to `FOUND_VIA_SEARCH` only if the existing status is `UNKNOWN` or `NOT_FOUND` (do not downgrade `FOUND_ON_WEBSITE` or `FOUND_IN_SCHEMA`)
- [x] 8.4 When creating stub leads from unmatched `SocialCandidate` objects, set `instagram_presence_status = FOUND_VIA_SEARCH` and `social_discovery_method = "search_fallback"` on the stub lead

## 9. Contact Discovery Extension for Social-Stub Leads

- [x] 9.1 In Stage 5b or post-stub-creation, check if a newly created social-stub lead has `website_url` non-null; if so, add it to a deferred contact-discovery queue
- [x] 9.2 After Stage 5b completes, run `ContactDiscovery.extract()` on queued social-stub leads using their `website_url`; apply results with fill-if-empty semantics (do not overwrite contacts already set from bio data)
- [x] 9.3 Run `EmailGuesser` on social-stub leads with a website URL if `all_emails` is still empty after stub contact discovery

## 10. Scoring Config Alignment

- [x] 10.1 Update `config/scoring_rules.json` — add `"contactability": 0.10` to `final_score_weights`; update `"website_problem"` to `0.30` and `"instagram_signal"` to `0.05` to match current code
- [x] 10.2 Modify `compute_final_score()` in `src/scoring/final_score.py` to accept an optional `weights: dict = None` parameter; when provided, use dict values with fallback to hardcoded defaults for missing keys
- [x] 10.3 In `LeadPipeline.__init__()`, load `scoring_rules.json` and extract `final_score_weights`; pass it to all `compute_final_score()` calls in the pipeline
- [x] 10.4 In `LeadPipeline.__init__()`, load `niches.json` and build a `niche_demand_weights: dict` mapping (niche name → `local_demand_weight`)
- [x] 10.5 Pass `niche_weight=niche_demand_weights.get(lead.niche, 1.0)` to all `compute_business_strength()` calls in the pipeline

## 11. Deduplicator Merge Extension

- [x] 11.1 Extend `_merge(winner, loser)` in `src/enrichment/deduplicator.py` to merge list fields: `all_emails`, `all_phones`, `whatsapp_links`, `messenger_links`, `booking_links`, `contact_form_urls`
- [x] 11.2 Use set-based deduplication for merged lists: case-insensitive for emails, E.164-normalized for phones (normalize via `normalize_phone()` before dedup)
- [x] 11.3 Extend `_merge()` to merge `source_platforms` list (union, deduplicated)
- [x] 11.4 Extend `_merge()` to backfill social URL fields (`instagram_url`, `facebook_url`, `tiktok_url`, `linkedin_url`, `youtube_url`, `pinterest_url`, `whatsapp_url`, `telegram_url`) from loser to winner when winner field is `None`

## 12. Export Extensions

- [x] 12.1 Add `instagram_presence_status` column to `COLUMNS` list in `src/output/exporter_csv.py` (appended after existing columns)
- [x] 12.2 Add `facebook_presence_status` column to `COLUMNS` list in `src/output/exporter_csv.py`
- [x] 12.3 Add `social_discovery_method` column to `COLUMNS` list in `src/output/exporter_csv.py`
- [x] 12.4 Ensure the CSV writer correctly handles enum values (call `.value` or `str()` on `SocialPresenceStatus` fields when emitting CSV rows)
- [x] 12.5 Verify `BusinessLead.to_json()` includes the three new fields (covered by task 1.5) by reviewing the JSON output of a test run

## 13. Validation and Testing

- [x] 13.1 Run `python -m pytest tests/ -v` — all existing tests must pass without modification
- [x] 13.2 Confirm `tests/test_scoring.py` still passes with the updated `scoring_rules.json` weights (weights haven't changed, only the JSON is being aligned)
- [x] 13.3 Confirm `tests/test_normalizer.py` still passes (no changes to normalizer)
- [x] 13.4 Confirm `tests/test_deduplicator.py` still passes; add a new test case covering list-field merging in `_merge()`
- [x] 13.5 Add a smoke-test or integration test that runs a mini pipeline config and verifies `instagram_presence_status` and `facebook_presence_status` are populated in output (not `UNKNOWN`) for a lead with a website
- [ ] 13.6 Run `python _smoke_tests.py` with a real API key to confirm the full pipeline produces output with the new fields populated
