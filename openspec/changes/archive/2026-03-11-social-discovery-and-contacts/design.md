## Context

The existing pipeline discovers SMB lead candidates exclusively through the OSM/Overpass API (with a fallback shim for Google Places). `SocialCollector` already extracts email and social profile URLs from *already-fetched* website HTML and OSM tags — but it cannot discover businesses that are absent from OSM. Instagram and Facebook together contain millions of SMBs that never claimed an OSM entry, particularly in the restaurant, beauty, and retail niches targeted by this project.

Current architecture:
- **Discovery**: `OverpassCollector` → niche × city → list of OSM place dicts
- **Enrichment 1**: `WebsiteCollector` → HTTP fetch, status
- **Enrichment 2**: website auditors (technical, SEO, UX)
- **Enrichment 3**: `InstagramSignalCollector` → signal-only (active / inactive / not found)
- **Enrichment 4**: `SocialCollector` → email + social URLs from HTML + OSM tags
- **Scoring**: 4 sub-scores → final priority + tier
- **Output**: JSON + CSV flat files (no relational DB / Alembic)

All data is held in memory during a run and serialised to `output/leads.json` at the end. There is no persistent database. Changes to the storage layer are therefore scope-free — we extend the `BusinessLead` dataclass and `to_json()` only.

## Goals / Non-Goals

**Goals:**
- Add Instagram as an independent discovery source (not just enrichment)
- Add Facebook as an independent discovery source (not just enrichment)
- Cross-match social-discovered candidates with existing OSM leads; merge when confident
- Preserve social-first leads even without an OSM/Places counterpart
- Structured extraction of all public contact channels (email, phone, WhatsApp, booking link, contact form, Linktree, Messenger)
- `contactability_score` (0–100) as a new sub-score
- `match_confidence` field per lead
- Feature-flag-gated: `enable_social_discovery`, `enable_contact_discovery`

**Non-Goals:**
- Authenticated Instagram Graph API integration (requires app review; out of scope)
- Relational DB / Alembic migrations (project stores leads as flat JSON/CSV)
- Guessing or constructing email addresses from domains
- Web scraping that requires session cookies or login
- Real-time / streaming pipeline changes

## Decisions

### D1 — Social discovery via public search endpoints only
**Decision**: Use only publicly accessible, no-auth endpoints for Instagram and Facebook discovery: public Hashtag/Place search pages (HTML scraping), Google site-search for `site:instagram.com niche city`, and OSM `contact:instagram` / `contact:facebook` tags already in-memory.

**Rationale**: The Instagram Graph API requires app review and a Facebook Business account; the unofficial private API violates ToS and is fragile. Public-page HTML scraping and Google-indexed profiles are stable, require no credentials, and respect the "no fake contacts" rule.

**Alternative considered**: python-instagram / instaloader — rejected due to ToS risk and account ban exposure.

**Implication**: Social discovery yield will be lower than a full API integration, but pipeline reliability is preserved. The collector is designed as pluggable so a real API adapter can be dropped in later.

### D2 — `SocialCandidate` as a thin intermediate model
**Decision**: Introduce a `SocialCandidate` dataclass (not a Pydantic model) holding: `source_platform`, `handle_or_page_id`, `display_name`, `city`, `country`, `niche`, `website_url`, `phone`, `email`, `social_urls: dict`. After matching, it either merges into an existing `BusinessLead` or is promoted to a new one.

**Rationale**: Keeps the discovery-to-lead pipeline symmetric with OSM candidates and avoids polluting `BusinessLead` with half-populated social-only fields before matching.

### D3 — Confidence-based matching, not aggressive merging
**Decision**: `CrossSourceMatcher` produces a `MatchResult(confidence, matched_lead_index)` per candidate. Only `HIGH` matches trigger field-merge into the existing lead. `MEDIUM` and `LOW` matches annotate the candidate but still create a new lead (with `match_confidence` recorded).

**Rationale**: False-positive merges (e.g. two "Café Roma" entries in the same city) corrupt existing high-quality OSM leads. The cost of a duplicate is lower than the cost of a corrupted record.

Confidence rules:
- **HIGH**: normalised name similarity ≥ 0.85 AND (phone match OR domain match OR social URL match)
- **MEDIUM**: normalised name similarity ≥ 0.70 AND city match
- **LOW**: name similarity ≥ 0.55 AND city match
- **UNMATCHED**: below LOW threshold

### D4 — ContactDiscovery runs after website fetch, reuses cached HTML
**Decision**: `ContactDiscovery.extract()` accepts the already-fetched `website_response` (requests.Response or None) plus the social URLs already stored on the lead. It does not make additional HTTP requests for pages that were already audited.

**Rationale**: The website HTML is already in memory after Stage 3 (WebsiteCollector). Re-fetching wastes time and risks rate-limits. Contact pages (`/contact`, `/about`, `/reservations`) are fetched as a *second* targeted request only when the main page yields no email.

### D5 — `contactability_score` is a lightweight additive sub-score
**Decision**: `contactability_score` is computed from a simple channel-count formula:

```
contactability = base_from_channels + quality_bonus
channels: email=30, phone=20, booking_link=15, contact_form=10,
          whatsapp=10, messenger=5, instagram_dm=5, facebook_msg=5
cap at 100
```

It contributes **10%** to the final `lead_priority_score` (current instagram_signal weight reduced from 10% to 5%; contactability takes the freed 5% plus a new 5% from rounding the formula).

**Rationale**: Keeps the existing scoring stable while giving contactable social-first leads a fair ranking boost.

### D6 — Feature flags in config, not env vars
**Decision**: `enable_social_discovery: false` and `enable_contact_discovery: false` in `config/run_europe_smb.json`. When absent or false, the pipeline behaves exactly as today (backward compatible).

## Risks / Trade-offs

- **[Risk] Instagram/Facebook HTML structure changes** → Mitigation: collector returns empty results gracefully; pipeline continues via OSM. Add version-stamped CSS selector constants so breakage is localised.
- **[Risk] Rate-limit / IP block from social platforms** → Mitigation: configurable `social_request_delay` (default 3s); randomised user-agent rotation; exponential backoff identical to Overpass collector. If blocked, collector returns empty list (no pipeline crash).
- **[Risk] Low social discovery yield** → Mitigation: treat as additive; OSM remains primary. Even 5–10% new leads per run is valuable.
- **[Risk] Contact page fetches add latency** → Mitigation: only fetch `/contact` subpage when main page has no email AND `enable_contact_discovery=true`. Capped at 1 extra request per lead with a 5s timeout.
- **[Risk] Cross-source matcher produces false positives** → Mitigation: D3 (conservative HIGH threshold); duplicate leads are cleaned by existing `deduplicate_leads()` pass at end of pipeline.
