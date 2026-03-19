## 1. Foundation — Models, Enums, Config

- [x] 1.1 Rewrite `src/enums.py`: define `WebsiteStatus` and `InstagramStatus` enums with all documented values
- [x] 1.2 Rewrite `src/models.py`: define `InputConfig`, `RawBusinessRecord`, `EnrichedRecord`, `AuditResult`, `ScoredLead` Pydantic models matching the result schema
- [x] 1.3 Create `config/niches.json`: controlled vocabulary for niche categories
- [x] 1.4 Create `config/scoring_rules.json`: scoring weights, thresholds, niche-bonus values, city-attractiveness table
- [x] 1.5 Extend `config/markets.json` to support the full input config format (countries, cities, niches, thresholds, flags)

## 2. Lead Discovery

- [x] 2.1 Implement `src/collectors/google_places_collector.py`: generate niche × city query strings and call Google Places Text Search API
- [x] 2.2 Add Place Details fetch in `google_places_collector.py`: retrieve all required fields per `place_id` (name, address, phone, website, rating, reviews count, map URL, business status, types)
- [x] 2.3 Implement filter logic in collector: exclude `PERMANENTLY_CLOSED`, enforce `min_reviews_threshold` and `min_rating_threshold` from input config
- [x] 2.4 Implement rate-limiting and per-request delay in collector (configurable)
- [x] 2.5 Write unit tests for query generation and filter logic in `tests/test_google_places_collector.py`

## 3. Business Enrichment

- [x] 3.1 Implement `src/enrichment/normalizer.py`: phone → E.164, URL → root domain, name → normalised lowercase, types → controlled vocabulary category
- [x] 3.2 Add social/directory domain detection to `normalizer.py`: classify `website_url` as `SOCIAL_ONLY` when it resolves to a known social domain list
- [x] 3.3 Create `src/enrichment/domain_resolver.py`: extract root domain from raw URL, handle www vs bare domain, strip paths and query strings
- [x] 3.4 Write unit tests for normalisation functions in `tests/test_normalizer.py`

## 4. Website Audit

- [x] 4.1 Implement `src/collectors/website_collector.py`: DNS resolution check, HTTP fetch with timeout, SSL validity check, redirect chain follow, parking-page fingerprint detection; produce `website_status`
- [x] 4.2 Create `src/auditors/technical_auditor.py`: HTTPS redirect check, mobile viewport meta tag, SSL validity flag, response time signal
- [x] 4.3 Create `src/auditors/seo_auditor.py`: title tag, meta description, H1 count, robots.txt presence, canonical tag
- [x] 4.4 Create `src/auditors/ux_auditor.py`: CTA keyword pattern detection, `href="tel:"` click-to-call detection, `<form` presence, WhatsApp link detection, booking keyword patterns
- [x] 4.5 Aggregate `issues_found` and `improvement_opportunities` lists from all three auditors
- [x] 4.6 Skip audit entirely (set all audit fields to null) when `website_status` is not `HAS_WEBSITE`
- [x] 4.7 Write unit tests for each auditor with fixture HTML samples in `tests/test_auditors.py`

## 5. Instagram Signal Analysis

- [x] 5.1 Implement handle discovery in `src/collectors/instagram_signal_collector.py`: extract Instagram handle from website HTML `<a href>` links
- [x] 5.2 Implement unauthenticated public profile fetch: GET `https://www.instagram.com/<handle>/` with browser-like User-Agent; parse post-count signal and link-in-bio indicator
- [x] 5.3 Implement `instagram_status` classification logic covering all five enum values including the `UNKNOWN` fallback on fetch failure
- [x] 5.4 Compute `instagram_signal_score` (0–100) from status tier and detected signals per scoring rules
- [x] 5.5 Write unit tests for status classification logic with mocked HTTP responses in `tests/test_instagram_signal.py`

## 6. Lead Scoring

- [x] 6.1 Implement `src/scoring/business_strength.py`: score from `reviews_count`, `rating`, niche value, city attractiveness; handle null inputs with default low score
- [x] 6.2 Implement `src/scoring/website_problem.py`: score from `website_status` enum and issue count
- [x] 6.3 Implement `src/scoring/commercial_opportunity.py`: score with niche-dependency bonus, active-Instagram-but-no-website bonus
- [x] 6.4 Implement `src/scoring/final_score.py`: compute weighted `lead_priority_score`; assign tier (1–4)
- [x] 6.5 Write unit tests for each scorer and the weighted formula in `tests/test_scoring.py`

## 7. Deduplication

- [x] 7.1 Implement `src/enrichment/deduplicator.py`: detect duplicates by `place_id`, `root_domain`, `normalised_phone`, and name+city Levenshtein similarity ≥ 0.90
- [x] 7.2 Implement merge logic: keep base record with most non-null fields; backfill missing fields from secondary record
- [x] 7.3 Run deduplication as a post-collection batch pass after all queries complete
- [x] 7.4 Write unit tests for all four identity keys and merge logic in `tests/test_deduplicator.py`

## 8. Outreach Generation

- [x] 8.1 Create `src/prompts/outreach_prompt.txt` and `src/prompts/system_prompt.txt` with the system and task prompts from the specification
- [x] 8.2 Implement rule-based `outreach_angle` generator in `src/` (or a dedicated `outreach_generator.py`): use evidence-based formula combining strength signal + gap signal
- [x] 8.3 Implement rule-based `short_pitch` generator: niche-aware templates, 1–3 sentences, no pressure language, concrete benefit mention
- [x] 8.4 Write unit tests for angle and pitch generation in `tests/test_outreach.py`

## 9. Pipeline Wiring and Output

- [x] 9.1 Rewrite `src/pipeline.py`: wire all six stages in order (discovery → enrichment → website audit → Instagram signal → scoring → deduplication → outreach generation)
- [x] 9.2 Update `src/main.py`: load input config from file or CLI args, run pipeline, pass result to exporter
- [x] 9.3 Create `src/output/exporter_json.py`: write validated JSON array to stdout or a configured output file
- [x] 9.4 Create `src/output/exporter_csv.py`: flatten result schema to CSV rows when `output_format` is `csv`
- [x] 9.5 Add `data/`, `logs/` directories with `.gitkeep` files
- [x] 9.6 Write an end-to-end smoke test in `tests/test_pipeline_smoke.py` using mocked external calls

## 10. Configuration and Documentation

- [x] 10.1 Create or update `requirements.txt` (or `pyproject.toml`) with all required dependencies: `requests`, `dnspython`, `beautifulsoup4`, `pydantic`, `python-levenshtein`, `phonenumbers`, `tldextract`
- [x] 10.2 Add `README.md` with setup instructions, input config format, example run command, and output schema reference
- [x] 10.3 Add `config/scoring_rules.json` defaults and document how to tune weights
