## Context

The pipeline currently has six fully-implemented modules that are never called: `SocialCollector` (multi-platform social link extraction from HTML), `EmailGuesser` (MX-verified domain-pattern guessing), `OverpassCollector` (OSM/Places-compatible fallback), `TripAdvisorCollector` (hospitality discovery), a JSON-LD schema.org presence check in `seo_auditor.py` that stops at detection without parsing, and a `ContactType`/`ContactCategory` enum pair in `models.py` with no attached data.

Meanwhile, the pipeline's social-discovery path (`InstagramDiscoveryCollector`, `FacebookDiscoveryCollector`) uses Google site-search as its **primary** method for finding social profiles — even for businesses that have working websites and already link their Instagram/Facebook on those pages. This is architecturally inverted: the cheapest, highest-confidence source (the business's own website) is ignored in favour of a rate-limited, lower-confidence search approach.

This design reconnects the unused modules and re-orders the enrichment pipeline so that social and contact data flows from best source to worst source: website → JSON-LD → Linktree hub → search fallback.

---

## Goals / Non-Goals

**Goals:**
- Wire `SocialCollector.extract_from_html()` into Stage 3 of the pipeline so all 9 social platforms are extracted from website HTML as a first step.
- Add a `JsonLdExtractor` module that parses `<script type="application/ld+json">` blocks in already-fetched HTML to extract phone, email, address, and `sameAs` social URLs — zero additional HTTP requests.
- Add Linktree/hub resolution: when a social link found in HTML points to a known link-hub domain (`linktr.ee`, `beacons.ai`, `bio.site`, etc.), fetch that page and re-run `SocialCollector` extraction on it.
- Demote search-based social discovery (`InstagramDiscoveryCollector`, `FacebookDiscoveryCollector`) to a fallback that only activates per-lead when the website-first and JSON-LD paths found no social presence.
- Add `SocialPresenceStatus` enum and `instagram_presence_status` / `facebook_presence_status` / `social_discovery_method` fields to `BusinessLead` to record discovery provenance.
- Wire `EmailGuesser` as a post-contact-discovery fallback when no email was found and a website domain is known.
- Wire `OverpassCollector` as a transparent fallback when `GooglePlacesCollector` raises an authentication or quota error.
- Align `scoring_rules.json` with code: add `contactability` weight (0.10), fix `website_problem` (0.30) and `instagram_signal` (0.05), and wire `niches.json` `local_demand_weight` into `compute_business_strength()`.
- Extend deduplicator `_merge()` to backfill contact list fields (`all_emails`, `all_phones`, `whatsapp_links`, `booking_links`, `contact_form_urls`) and `source_platforms` from secondary records.
- Add new export columns: `instagram_presence_status`, `facebook_presence_status`, `social_discovery_method`.

**Non-Goals:**
- Meta Graph API / Instagram Graph API / Facebook Graph API integration. The data from those APIs would be high-quality but requires app review and credentials the project does not have. This remains a future phase.
- Typed `Contact` dataclass with per-contact source attribution (the `ContactType`/`ContactCategory` enum approach). That redesign touches every test and export and is too high risk for this change. The flat-list contact fields (`all_emails`, `all_phones`, etc.) are retained.
- Playwright/Selenium or JS rendering. All website fetch operations use `requests` + BeautifulSoup on raw HTML. JavaScript-rendered content is out of scope.
- TripAdvisor discovery wiring. `TripAdvisorCollector` is implemented but wiring into the pipeline requires a separate investigation into conflict and dedup logic.
- Full rate-limit budget tracking across all collectors. A simple per-lead guard (skip search if social already found) covers the primary abuse surface with minimal complexity.

---

## Decisions

### Decision 1: Run `SocialCollector` before `InstagramSignalCollector`, not alongside it

**Choice:** Call `SocialCollector.extract_from_html(html, base_url)` at the start of Stage 3 (after website status is confirmed as `HAS_WEBSITE`). Apply the extracted `instagram` URL to `lead.instagram_url` and the other platform URLs to their respective fields. Then pass the handle to `InstagramSignalCollector.analyze_handle()` to get the `InstagramStatus` quality signal (ACTIVE, INACTIVE, etc.). The existing `extract_handle_from_html()` call in `InstagramSignalCollector` is retired — `SocialCollector`'s result feeds it instead.

**Rationale:** `InstagramSignalCollector.extract_handle_from_html()` does a single `<a href>` scan for Instagram specifically. `SocialCollector.extract_from_html()` covers 9 platforms with more comprehensive patterns including `<meta>` tags and multiple link variants. Running both would duplicate work. The `InstagramStatus` quality signal (post count, bio link) is still valuable and is retained — we just remove the redundant handle extraction step.

**Alternative considered:** Keep `InstagramSignalCollector.extract_handle_from_html()` as-is and have `SocialCollector` supplement it. Rejected because it creates two code paths for the same field with potential divergence.

---

### Decision 2: JSON-LD extractor as a new module in `src/enrichment/`

**Choice:** Create `src/enrichment/json_ld_extractor.py` with a single function `extract_from_html(html: str) -> dict` that returns a dict with keys `phone`, `email`, `address`, `social_urls` (list of URLs from `sameAs`), `name`, `opening_hours`, `price_range`. Called in Stage 3 after `SocialCollector` extraction, before `ContactDiscovery`. Results are merged into lead fields with "fill if empty" semantics — never overwrite existing non-null values.

**Rationale:** JSON-LD is in the already-fetched HTML response. Parsing it is a stdlib-only `json.loads()` with BeautifulSoup for tag finding — zero new dependencies, zero extra HTTP requests. `sameAs` arrays in schema.org LocalBusiness often contain Instagram, Facebook, TripAdvisor, and Yelp URLs with zero ambiguity.

**Alternative considered:** Extend `seo_auditor.py` to parse JSON-LD since it already scans for it. Rejected because `seo_auditor.py` produces issue lists, not enrichment data, and mixing concerns would make it harder to skip audit in non-audit runs.

---

### Decision 3: Linktree resolution in the pipeline stage, not inside `SocialCollector`

**Choice:** After `SocialCollector.extract_from_html()` runs, check if any extracted social URL (or the website URL itself) matches a known hub domain set (`linktr.ee`, `beacons.ai`, `bio.site`, `solo.to`, `taplink.cc`). If so, make one additional GET request (timeout ≤ 5s) to that URL, and re-run `SocialCollector.extract_from_html()` on the result. Apply any newly discovered URLs that weren't already set. Gated on new config flag `enable_linktree_resolution` (default `true`).

**Rationale:** `SocialCollector` is designed to parse a single page. Keeping the hub-follow logic in the pipeline stage preserves single responsibility and makes it easy to gate, log, and disable. Limiting to one re-fetch prevents infinite expansion.

**Alternative considered:** Build hub resolution into `SocialCollector` itself. Rejected because it couples HTTP fetching into a module that receives already-fetched HTML in its primary interface.

---

### Decision 4: Demote search discovery with a per-lead presence check

**Choice:** In Stage 5b, before calling `InstagramDiscoveryCollector.search()` for a lead's niche × city combination, check if `lead.instagram_url` is already populated (from Stage 3 website/JSON-LD extraction). If it is, skip the Instagram search for that lead. Apply the same logic for `FacebookDiscoveryCollector` and `lead.facebook_url`. The search still runs for the niche × city query as a whole to discover NEW businesses (social-first candidates), but the per-lead enrichment path skips it when a social URL is already known.

**Rationale:** The existing Stage 5b architecture runs social discovery per niche × city, not per individual lead. Matching and merging are already handled by `CrossSourceMatcher`. The minimal change is to add the presence check so that a lead that already has `instagram_url` does not trigger a social discovery batch unnecessarily, while social-first candidate discovery (finding businesses that only appear on Instagram/Facebook) continues to work.

**Alternative considered:** Move all social discovery to Stage 3 as a per-lead operation. Rejected because the current niche × city grouping is more efficient (one search covers N leads) and Changing the architecture at this point would be high risk.

---

### Decision 5: `SocialPresenceStatus` as two per-platform fields, not a single dict

**Choice:** Add `instagram_presence_status: SocialPresenceStatus = UNKNOWN` and `facebook_presence_status: SocialPresenceStatus = UNKNOWN` as typed fields on `BusinessLead`, plus `social_discovery_method: Optional[str]` for a human-readable free-text record of the last significant discovery path. The enum has six values: `FOUND_ON_WEBSITE`, `FOUND_IN_SCHEMA`, `FOUND_VIA_HUB`, `FOUND_VIA_SEARCH`, `NOT_FOUND`, `UNKNOWN`.

**Rationale:** Two concrete typed fields are simpler to export, test, and filter than a `Dict[str, SocialPresenceStatus]`. Instagram and Facebook are the only two platforms where provenance tracking is currently meaningful. Adding fields for 9 platforms would bloat the model without downstream value.

**Alternative considered:** A single `social_presence_status: Dict[str, SocialPresenceStatus]` dict. Rejected because dicts are harder to serialise consistently in CSV and harder to reference in scoring rules.

---

### Decision 6: Load scoring weights from `scoring_rules.json` at pipeline init, not at import time

**Choice:** `compute_final_score()` in `final_score.py` keeps its current signature but will accept an optional `weights: dict` parameter. The pipeline loads `scoring_rules.json` once at init and passes the `final_score_weights` section to `compute_final_score()` on each call. Hardcoded weights become the fallback defaults. `scoring_rules.json` will be updated to include `contactability: 0.10` and to align `website_problem` (0.30) and `instagram_signal` (0.05) with the code's current values.

**Rationale:** This makes the JSON file the actual source of truth without restructuring all modules. The optional `weights` parameter is backward-compatible — every existing call site works with no changes.

**Alternative considered:** Import `scoring_rules.json` inside `final_score.py` directly. Rejected because it adds an implicit file-system dependency to a pure computation module and would break tests that call `compute_final_score()` directly.

---

## Risks / Trade-offs

**[Risk] `SocialCollector` replaces `InstagramSignalCollector.extract_handle_from_html()` — result differences may affect some leads**
→ Mitigation: `SocialCollector`'s Instagram pattern is at least as broad. Run the existing test suite for Instagram extraction. Accept that a small number of edge-case handles (excluded by `SocialCollector`'s generic-path filter but found by the old heuristic) may differ. The quality signal path (`analyze_handle`) is unchanged.

**[Risk] Linktree resolution adds a second HTTP request for a subset of leads**
→ Mitigation: gated by `enable_linktree_resolution` flag; timeout is capped at 5s; only one follow-up fetch per lead; hub domain list is a fixed allowlist, not a pattern match, preventing abuse.

**[Risk] JSON-LD parsing may overwrite correct existing data with wrong JSON-LD if a site has multiple `@type` entities**
→ Mitigation: `extract_from_html()` scores entities by `@type` specificity (prefers `LocalBusiness`, `Restaurant`, `MedicalBusiness` over generic `Organization`); uses "fill if empty" merge — never overwrites existing non-null values on the lead.

**[Risk] Deduplicator merge extension may cause list field duplication if the same email appears in both winner and loser**
→ Mitigation: `_merge()` already computes richer-record winner by non-null count; extend it to merge lists with set-based deduplication (case-insensitive for emails, E.164-normalised for phones).

**[Risk] Scoring weight change from `scoring_rules.json` loading may change lead tiers in existing test output fixtures**
→ Mitigation: The spec-specified formula weights (`0.30, 0.30, 0.25, 0.05, 0.10`) are not changing — the `scoring_rules.json` is being updated to match the code, not the other way around. Test fixtures should not change.

---

## Migration Plan

All changes are in the Python source only — no database, no external API contract, no network-protocol change.

1. Create `src/enrichment/json_ld_extractor.py` (new file, no existing callers).
2. Add `SocialPresenceStatus` to `src/enums.py` and the three new fields to `src/models.py` / `BusinessLead.to_json()`.
3. Wire `SocialCollector` + `JsonLdExtractor` + Linktree resolver into Stage 3 of `pipeline.py`.
4. Track `instagram_presence_status` / `facebook_presence_status` as each source populates social URLs.
5. Wire `EmailGuesser` post-contact-discovery in Stage 3c.
6. Wire `OverpassCollector` as Places error fallback in Stage 1.
7. Extend deduplicator `_merge()`.
8. Update `scoring_rules.json`; update `final_score.py` to accept optional weights dict; pass loaded weights from pipeline.
9. Wire `local_demand_weight` from `niches.json` into `compute_business_strength()` calls.
10. Add new columns to `exporter_csv.py`; add new fields to `to_json()`.
11. Run full test suite; add targeted tests for JSON-LD extractor and `SocialPresenceStatus`.

**Rollback:** Every wiring change is gated by existing config flags or new flags with safe defaults. Reverting means removing the new pipeline calls — no data migration needed.

---

## Open Questions

- Should `SocialCollector` extract `whatsapp_url` and populate `lead.whatsapp_url`, or should this continue to be handled exclusively by `ContactDiscovery.extract()`? Recommendation: let `SocialCollector` populate `lead.whatsapp_url` (the single canonical URL from the website) while `ContactDiscovery` populates `lead.whatsapp_links` (the full list with context). No conflict since they target different fields.
- Should `EmailGuesser` be called for social-stub leads (those with no `website_url` from Places but with a bio-discovered URL)? Current answer: yes — if `lead.website_url` is non-null and `all_emails` is empty, `EmailGuesser` runs regardless of lead source.
- Should `OverpassCollector` fallback be automatic (on quota/auth error) or require explicit config flag? Current answer: automatic on error, with a warning logged. No config flag needed since it's a transparent fallback with no quality difference to the caller.
