## Context

The current repository has reusable JSON configs under `config/`, but the bundled examples target Spain, Portugal, and the Netherlands. The active fallback collector in this codebase is Overpass/OpenStreetMap, and it only supports a defined niche vocabulary in `src/collectors/overpass_collector.py`. That means a Ukraine preset should prefer niches that are both commercially attractive for website sales and already supported by the collector, rather than introducing unsupported service categories that would produce empty or failed queries.

The requested geography is fixed: Kyiv, Lviv, Kharkiv, Odesa, and Ivano-Frankivsk. The design therefore focuses on packaging those cities into a practical preset with language priorities and a niche mix suitable for SMB website creation, redesign, local SEO, ordering, and booking improvements.

## Goals / Non-Goals

**Goals:**
- Add a ready-to-run Ukraine configuration file under `config/`.
- Use the exact city set requested by the operator.
- Select niches that align with common website/CRO pain points and the current Overpass niche map.
- Keep the preset safe to run without code changes or collector expansion.
- Make output paths and runtime defaults explicit so campaign results are isolated from existing Europe runs.

**Non-Goals:**
- Expanding the collector to new Ukrainian-specific verticals such as dentists, lawyers, or clinics.
- Changing lead scoring formulas or enrichment logic.
- Localizing prompts, scoring copy, or audit heuristics for the Ukrainian language.
- Creating multiple Ukraine presets for different budget tiers in this change.

## Decisions

### Decision: Ship a dedicated preset file instead of modifying an existing Europe config
The change will add a standalone file such as `config/run_ukraine_smb.json`. This keeps the operator workflow simple, avoids regressions in existing Europe presets, and makes campaign outputs easier to separate.

Alternative considered:
- Reusing `run_europe_smb_full_unbounded.json` and swapping values in place. Rejected because it would mix markets and make repeatable campaign execution harder.

### Decision: Use an OSM-compatible niche list with strong website ROI
The preset will prefer these niches:
- `beauty salon`
- `restaurant`
- `bakery`
- `florist`
- `boutique`
- `cosmetics shop`
- `pet shop`
- `home decor shop`

These niches were chosen because they map cleanly to current collector tags and regularly benefit from websites or website improvements such as online booking, menus, catalog pages, click-to-call/contact flows, local SEO landing pages, and seasonal campaign pages.

Alternatives considered:
- Service-heavy niches from `config/niches.json` such as `dentist`, `lawyer`, or `physiotherapy`. Rejected for this preset because the current Overpass fallback does not map them, which would create unreliable runs when Google Places is unavailable.
- A larger niche list including every supported retail category. Rejected to keep query volume focused on the most commercially promising verticals.

### Decision: Favor low filtering thresholds for outreach discovery
The preset will keep `min_reviews_threshold` at `0` and `min_rating_threshold` at `0.0`. For website sales, businesses with weak review profiles can still be valid prospects if they lack a modern website, conversion flow, or contact path.

Alternative considered:
- Requiring review and rating minimums. Rejected because that would bias the preset toward already-mature businesses and shrink the reachable lead pool.

### Decision: Prioritize Ukrainian first, then English, then Russian
The preset will use `language_priority: ["uk", "en", "ru"]`. Ukrainian should be primary for modern local-market sites, English helps tourism-facing and export-oriented businesses, and Russian remains useful as a fallback for older websites in legacy markets.

Alternative considered:
- English-first language priority. Rejected because it does not reflect the current local-market default for Ukraine-focused SMB outreach.

### Decision: Enable enrichment features that improve sellability analysis
The preset will enable website audit, social discovery, contact discovery, and email guesser by default. TripAdvisor discovery will remain enabled because the collector already self-limits to hospitality niches and can improve restaurant coverage without affecting non-hospitality queries.

Alternative considered:
- Disabling optional enrichments for faster runs. Rejected because the user request is about finding saleable website opportunities, and those enrichments materially improve pitch quality.

## Risks / Trade-offs

- [Risk] Some requested website-friendly SMB niches in Ukraine are not supported by the current Overpass niche map. → Mitigation: constrain the preset to supported categories and note collector expansion as future work.
- [Risk] Kharkiv and Odesa query coverage may vary by OSM completeness and current business activity. → Mitigation: keep thresholds permissive and preserve multi-city coverage rather than overfitting to one city.
- [Risk] Enabling social/contact enrichment increases runtime across 40 niche-by-city queries. → Mitigation: keep the niche list focused and set explicit output files so long runs remain manageable and reviewable.
- [Risk] A single preset cannot optimize equally for hospitality, retail, and beauty businesses. → Mitigation: bias the selection toward categories where website or redesign value is easiest to communicate in outbound campaigns.

## Migration Plan

No data migration is required. Operators can run the new preset alongside existing configs and compare output quality independently. If the preset proves too broad, it can be narrowed later without affecting the existing Europe presets.

## Open Questions

- Should a second Ukraine preset later be added for service businesses once Overpass support exists for dentists, clinics, legal firms, and similar higher-ticket niches?
- Should `README.md` expose this preset immediately, or should documentation wait until the config has been validated on a live run?
