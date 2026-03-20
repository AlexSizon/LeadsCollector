## Why

The pipeline currently relies on a single-language niche label per market, which limits discovery coverage in multilingual markets and makes category-language choice disproportionately important. We need an explicit multilingual search mechanism so the pipeline can generate lead-discovery queries across multiple languages while keeping a stable canonical niche model underneath.

## What Changes

- Add a multilingual search-language configuration field for pipeline runs so operators can specify which languages should be used to search for leads.
- Add a localized niche vocabulary covering Dutch, English, Spanish, Portuguese, German, Ukrainian, and Russian for supported SMB categories.
- Expand lead discovery so query generation can search the same niche and city across multiple configured languages instead of a single category phrase.
- Preserve canonical niche normalization and output schema while deduplicating multilingual discovery results across repeated businesses.
- Update the Ukraine market preset so its lead-search languages are explicitly `["en", "uk", "ru"]`.

## Capabilities

### New Capabilities
- `localized-search-vocabulary`: Maintain a language-to-category vocabulary map that translates supported canonical niches into localized search phrases for multilingual lead discovery.

### Modified Capabilities
- `lead-discovery`: Extend query generation and config handling to support multilingual search inputs via a dedicated search-language field.
- `market-presets`: Allow bundled market presets to define market-specific lead-search languages separately from language-priority settings.

## Impact

- `config/`: Add a new pipeline config field for multilingual lead-search languages; update relevant bundled presets.
- `config/niches.json` or related config data: Store localized search labels for the supported languages `nl`, `en`, `es`, `pt`, `de`, `uk`, and `ru`.
- `src/pipeline.py` and `run_europe_smb.py`: Generate search queries per configured search language and keep deduplication/reporting coherent across expanded query volume.
- Collectors and tests: Validate that multilingual queries still map back to supported canonical niches and do not break OSM/Google/social discovery flows.
