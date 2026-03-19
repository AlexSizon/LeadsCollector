## Context

The project already contains a partial skeleton (`src/pipeline.py`, `src/models.py`, `src/enums.py`, `src/collectors/`, `src/enrichment/`, `src/scoring/`, `config/markets.json`). The goal is to build out those modules into a fully functional pipeline that discovers, audits, scores, and generates outreach data for European SMBs.

The system runs as a CLI-triggered batch job: read input config → collect leads → enrich → audit → score → deduplicate → export. There is no web server or real-time API requirement for the MVP.

External dependencies:
- **Google Places API** (Text Search + Place Details): primary discovery and metadata source
- **HTTP / DNS checks** (requests, dnspython): website presence and health
- **Public Instagram web signals**: lightweight heuristics against the public profile page — no private API access, no authentication required

## Goals / Non-Goals

**Goals:**
- Complete the existing partial skeleton into a working end-to-end pipeline
- Implement all six pipeline stages: discovery → enrichment → website audit → Instagram signal → scoring → outreach generation
- Produce a validated JSON array output conforming to the defined result schema
- Enforce deduplication across runs using four identity keys
- Mark all uncertain fields as `UNKNOWN` rather than fabricating values
- Support configurable input (countries, cities, niches, thresholds, flags)

**Non-Goals:**
- Real-time or streaming execution
- Authenticated Instagram API access (Graph API)
- Full Lighthouse / Puppeteer rendering-based audits (MVP uses HTTP + HTML heuristics)
- Multi-language pitch generation (English only for MVP)
- A web UI or REST API layer
- CRM integration or email sending

## Decisions

### D1: Pipeline stage isolation via typed Pydantic models

Each stage receives the output of the previous stage as a typed model. This makes each module independently testable and prevents implicit data coupling.

**Alternative considered**: Passing raw dicts between stages. Rejected because it makes it impossible to validate data shape at each boundary and increases the risk of silent data loss.

### D2: Google Places Text Search + Place Details (two-call pattern)

Discovery uses Text Search to get `place_id` lists, then Place Details to fetch full metadata per place. This keeps queries within the official API contract.

**Alternative considered**: Google Maps scraping. Rejected — fragile, against ToS, and violates the project's constraint to use only sustainable sources.

### D3: Website audit using requests + BeautifulSoup (not a headless browser)

The MVP website audit performs HTTP-level checks (status, SSL, redirects, headers) and HTML parsing heuristics (title, meta, h1, CTA patterns, mobile viewport tag). This is fast, requires no browser install, and sufficient for the problem signals we care about.

**Alternative considered**: Playwright/Puppeteer for full rendering. Deferred to post-MVP — adds significant complexity and latency; JS-rendered content is not required for the targeted heuristics.

### D4: Instagram signal via public profile HTTP fetch (unauthenticated)

Fetch `https://www.instagram.com/<handle>/` with a browser-like User-Agent and parse the returned HTML/JSON-LD for profile signals (business category, bio link, post count). No session, no API token.

**Alternative considered**: Instagram Graph API. Rejected — requires app review, user consent, and is not suitable for bulk analysis of arbitrary business accounts.

### D5: Scoring as four independent, normalised sub-scores (0–100) combined with fixed weights

Each sub-scorer returns a float in [0, 100]. The final score uses the formula:
```
lead_priority_score = 0.30 × business_strength + 0.35 × website_problem + 0.25 × commercial_opportunity + 0.10 × instagram_signal
```

**Alternative considered**: A single monolithic scoring function. Rejected — harder to tune, test, and explain. Independent scorers allow weight adjustment without touching audit logic.

### D6: Deduplication before export, keyed on four signals

Deduplication runs as a post-processing pass over the full collected list, merging records that share `place_id`, root domain, normalised phone, or high-confidence name+city match. The richer record (more non-null fields) is kept.

**Alternative considered**: Deduplication during collection. Rejected — cross-query duplicates are only detectable after all queries complete.

### D7: Output as JSON array to stdout + optional file

The default output is a JSON array written to stdout (or a configured file path). CSV export is available as a secondary option. This keeps the pipeline composable (pipe to jq, upstream tools, etc.).

## Risks / Trade-offs

- **[Google API quota]** → Text Search and Place Details have per-day quotas and per-request costs. The pipeline must enforce `max_results_per_query` and log consumed credits. Mitigation: implement a rate-limiter and dry-run flag.
- **[Instagram detection reliability]** → Instagram frequently changes its page structure, which can break HTML-based signal extraction. Mitigation: degrade gracefully to `UNKNOWN` status; never treat a failed fetch as `NOT_FOUND`.
- **[Website audit false positives]** → Heuristic-based CTA/booking detection can misclassify pages. Mitigation: use conservative keyword sets; mark ambiguous cases as `UNKNOWN` rather than a definitive negative.
- **[Rate limiting / IP blocking]** → Bulk website checks may trigger rate limits or CAPTCHAs. Mitigation: add configurable per-request delays and respect `robots.txt` for crawled content.
- **[Partial skeleton compatibility]** → Existing files in `src/` may have conflicting interfaces. Mitigation: treat the existing skeleton as a starting point; refactor models and enums first to establish the shared contract before implementing stage logic.

## Migration Plan

1. Refactor `src/enums.py` and `src/models.py` to match the agreed data schema
2. Implement collectors in dependency order: `google_places_collector.py` → `website_collector.py` → `instagram_signal_collector.py`
3. Implement enrichment: `normalizer.py` → `deduplicator.py` → add `domain_resolver.py`
4. Implement auditors: `technical_auditor.py` → `seo_auditor.py` → `ux_auditor.py`
5. Implement scoring modules (already partially stubbed)
6. Wire stages in `pipeline.py` and expose CLI entry point in `main.py`
7. Add `src/output/exporter_json.py` and `exporter_csv.py`
8. Add `config/niches.json` and `config/scoring_rules.json`
9. Add smoke tests in `tests/`

Rollback: the existing skeleton is not production-facing, so there is no rollback requirement for the MVP.

## Open Questions

- Should the pipeline support resuming from a checkpoint (e.g., skip already-audited domains)? Deferred to post-MVP.
- What is the target latency per lead? Need to establish a benchmark once the HTTP audit stage is complete.
- Should `outreach_generation` use an LLM call (e.g., OpenAI) or a rule-based template engine? Rule-based templates are used for MVP; LLM-based generation can be added later via a flag.
