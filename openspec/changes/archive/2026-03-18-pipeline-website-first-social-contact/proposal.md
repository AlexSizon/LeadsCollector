## Why

The lead pipeline currently relies on Google site-search as the primary method for discovering Instagram and Facebook presence, while a fully functional `SocialCollector` that extracts social links directly from business websites sits unused. This inverts the correct data-quality hierarchy: website-extracted social links are higher-confidence and free of rate-limit risk, yet search-based discovery runs at scale for every lead. The result is unnecessary API pressure, lower-quality social signal attribution, and several complete modules (`SocialCollector`, `EmailGuesser`, `OverpassCollector`, `TripAdvisorCollector`, JSON-LD parsing) that are implemented but never wired into the pipeline — leaving real data on the table for every run.

## What Changes

- **Wire `SocialCollector` as the primary social-link extraction path** for all leads with a working website — replacing the single-handle `InstagramSignalCollector` HTML scan with the full 9-platform extractor covering Instagram, Facebook, TikTok, LinkedIn, YouTube, Pinterest, WhatsApp, and Telegram.
- **Add JSON-LD / schema.org structured data extraction** (`src/enrichment/json_ld_extractor.py`) to pull business phone, email, address, opening hours, and `sameAs` social profile URLs from website HTML without additional HTTP requests.
- **Add Linktree resolution** — when a website's social links resolve to a Linktree-style hub (linktr.ee, beacons.ai, etc.), fetch that page and re-run social extraction to surface the downstream links.
- **Demote search-based social discovery to fallback only** — `InstagramDiscoveryCollector` and `FacebookDiscoveryCollector` run only for leads where website and JSON-LD extraction found no social presence.
- **Add `SocialPresenceStatus` tracking** — new enum and fields on `BusinessLead` recording HOW each social link was found: `FOUND_ON_WEBSITE`, `FOUND_IN_SCHEMA`, `FOUND_VIA_SEARCH`, `FOUND_VIA_HUB`, `NOT_FOUND`, `UNKNOWN`.
- **Wire `EmailGuesser`** into the pipeline as the configured fallback when contact discovery finds no email and a domain is known.
- **Wire Overpass as Places fallback** — `OverpassCollector` activates if `GooglePlacesCollector` raises a quota/auth error.
- **Fix scoring config drift** — align `final_score.py` weights, niche demand weights from `niches.json`, and `scoring_rules.json` so the JSON file is the actual source of truth.
- **Extend export fields** — add `social_presence_status`, `social_discovery_method`, and `instagram_presence_status` / `facebook_presence_status` to JSON and CSV outputs.
- **Extend deduplication merge** to backfill `all_emails`, `all_phones`, `whatsapp_links`, `booking_links`, `contact_form_urls`, and `source_platforms` from secondary records.

## Capabilities

### New Capabilities

- `json-ld-extraction`: Extract structured business data (phone, email, address, social URLs via `sameAs`, opening hours) from JSON-LD / schema.org blocks embedded in website HTML. Primary input to social and contact enrichment before any HTTP fallbacks.
- `social-presence-tracking`: Track and store the provenance of each discovered social profile using a `SocialPresenceStatus` enum (`FOUND_ON_WEBSITE`, `FOUND_IN_SCHEMA`, `FOUND_VIA_HUB`, `FOUND_VIA_SEARCH`, `NOT_FOUND`, `UNKNOWN`). Persisted on `BusinessLead` and exported.

### Modified Capabilities

- `social-discovery`: Website-first social link extraction (`SocialCollector`) becomes the primary method; JSON-LD `sameAs` fields are the second method; Linktree/hub resolution is the third method; search-based discovery is explicitly the fallback layer, activated only for unresolved leads.
- `contact-discovery`: JSON-LD extraction results feed into the contact pool alongside HTML scraping; `SocialCollector`-discovered links are the preferred source for social contact fields; social-stub leads (no website) also get contact extraction from bio-discovered URLs.
- `lead-scoring`: Niche demand weights from `niches.json` (`local_demand_weight`) are applied to `compute_business_strength()`; `scoring_rules.json` becomes the enforced source of truth for all composite score weights including `contactability`.
- `export-format`: Adds `social_presence_status`, `social_discovery_method`, `instagram_presence_status`, and `facebook_presence_status` to both JSON and CSV outputs; backward-compatible (new fields appended, no column renames).

## Impact

**Modified files:**
- `src/pipeline.py` — wire `SocialCollector`, JSON-LD extractor, Linktree resolver, `EmailGuesser`, `OverpassCollector` fallback; demote search discovery to fallback path; add `SocialPresenceStatus` tracking
- `src/enums.py` — add `SocialPresenceStatus` enum
- `src/models.py` — add `instagram_presence_status`, `facebook_presence_status`, `social_discovery_method` fields to `BusinessLead`; extend `to_json()`
- `src/scoring/business_strength.py` — accept and apply `niche_weight` from config
- `src/scoring/final_score.py` — read weights from `scoring_rules.json` instead of hardcoding; include `contactability` in config
- `src/enrichment/deduplicator.py` — extend `_merge()` to backfill contact lists and social fields
- `src/output/exporter_csv.py` — add new columns
- `config/scoring_rules.json` — add `contactability` weight, align all weights with code

**New files:**
- `src/enrichment/json_ld_extractor.py` — JSON-LD parser (~80 lines, stdlib only)

**Configuration:**
- New optional flags: `overpass_fallback` (default `true`), `enable_linktree_resolution` (default `true`)
- Existing flags respected: `enable_contact_discovery`, `enable_social_discovery`, `enable_email_guesser`

**Dependencies:** No new libraries required. All needed libs (`requests`, `beautifulsoup4`, `lxml`, `dnspython`) are already in `requirements.txt`.
