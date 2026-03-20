## Context

The current pipeline treats niche labels as both the canonical business category and the outward-facing search phrase. That works in single-language markets, but it breaks down in multilingual regions because category wording materially affects discovery coverage. The existing `language_priority` field also does not solve this problem cleanly: in `src/pipeline.py` it is used as the API response language for Google Places, while `run_europe_smb.py` does not use it to vary lead-search phrases at all.

This change introduces a separate concept for multilingual query generation. The pipeline needs one stable canonical niche model for scoring, deduplication, and exports, but it also needs localized category phrases for actual lead search. The requested supported search languages are Dutch (`nl`), English (`en`), Spanish (`es`), Portuguese (`pt`), German (`de`), Ukrainian (`uk`), and Russian (`ru`), with the Ukraine preset explicitly searching in English, Ukrainian, and Russian.

## Goals / Non-Goals

**Goals:**
- Add a dedicated config field for search languages used to find leads.
- Keep `language_priority` distinct from search-language expansion.
- Add a localized search vocabulary for the supported language set `nl`, `en`, `es`, `pt`, `de`, `uk`, and `ru`.
- Expand query generation across configured search languages while preserving canonical niche identity.
- Ensure the Ukraine preset declares `search_languages: ["en", "uk", "ru"]`.
- Preserve backward compatibility for existing configs that only define `language_priority`.

**Non-Goals:**
- Translating every city and country name variant for every locale.
- Reworking scoring, outreach generation, or website auditing to become multilingual.
- Guaranteeing identical coverage across all data sources; some collectors are tag-based or source-limited.
- Adding support for languages outside the requested set in this change.

## Decisions

### Decision: Introduce `search_languages` as a new config field
The pipeline will gain a dedicated `search_languages` field that controls multilingual lead-search expansion. `language_priority` remains responsible for response-language selection and other downstream language preferences.

Alternative considered:
- Reusing `language_priority` for both purposes. Rejected because it conflates API response language with search-query generation and would keep current behavior ambiguous.

### Decision: Keep canonical niches and add localized search labels beside them
Canonical niche keys remain the stable identifiers in configs, scoring, deduplication, and exported leads. Localized phrases will be stored as vocabulary data keyed by language code, likely alongside existing niche metadata in `config/niches.json`.

Alternative considered:
- Allowing fully free-form localized niche strings directly in `niches`. Rejected because it would weaken normalization, collector compatibility, and deduplication semantics.

### Decision: Expand query generation per `city × niche × search_language`
For discovery sources that rely on free-form text search, the pipeline will generate one query per configured search language using the localized niche phrase for that language. Internally, each query will still carry the same canonical niche identity so collected leads can be scored and deduplicated consistently.

Alternative considered:
- Searching only in the first configured language and treating the rest as fallback on zero results. Rejected because it makes coverage dependent on source ordering and obscures the search plan.

### Decision: Preserve compatibility when `search_languages` is absent
If a config does not define `search_languages`, the pipeline should continue to function by deriving a default from the existing configuration, such as the first `language_priority` entry or canonical English behavior.

Alternative considered:
- Making `search_languages` mandatory immediately. Rejected because it would break every existing preset and add migration friction without clear operator benefit.

### Decision: Update market presets independently from global language support
The multilingual vocabulary will support `nl`, `en`, `es`, `pt`, `de`, `uk`, and `ru`, but each market preset will explicitly declare only the languages it should search. For Ukraine, that set is `["en", "uk", "ru"]`.

Alternative considered:
- Auto-applying all supported languages to every market. Rejected because it would explode query counts and introduce irrelevant cross-language noise.

## Risks / Trade-offs

- [Risk] Query count grows multiplicatively with each added search language. -> Mitigation: keep search languages explicit per preset and log expanded query volume clearly.
- [Risk] Some localized labels may not map cleanly to OSM-tag-based collectors. -> Mitigation: preserve canonical niche identity separately from localized query phrases and keep collector-side canonical mapping intact.
- [Risk] Language variants can increase duplicate discovery of the same business. -> Mitigation: rely on existing deduplication keyed by place ID, domain, phone, and name/city similarity.
- [Risk] Vocabulary coverage will be incomplete for some niches or regions. -> Mitigation: define fallback behavior to canonical labels when a localized phrase is missing.

## Migration Plan

1. Add localized search-language vocabulary data for the supported language codes.
2. Extend pipeline config parsing to accept `search_languages` while preserving old configs.
3. Update query generation in `src/pipeline.py` and `run_europe_smb.py` to expand across search languages.
4. Update the Ukraine preset to declare `search_languages: ["en", "uk", "ru"]`.
5. Add tests verifying backward compatibility, multilingual query expansion, and preset configuration.

## Open Questions

- Should multilingual social discovery use localized city names in addition to localized niche names, or should this change stay focused on category-language expansion first?
- Should `query` log events include the active search language for operator observability, or is city+niche sufficient for the first version?
