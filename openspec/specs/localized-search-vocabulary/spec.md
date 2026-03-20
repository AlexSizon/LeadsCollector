# localized-search-vocabulary Specification

## Purpose
Define the supported multilingual niche search vocabulary used to expand canonical lead-search queries.

## Requirements

### Requirement: Repository provides localized niche search labels for supported languages
The repository SHALL provide a localized search vocabulary that maps supported canonical niche identifiers to lead-search phrases for the supported language codes `nl`, `en`, `es`, `pt`, `de`, `uk`, and `ru`.

#### Scenario: Supported language set is available
- **WHEN** the localized search vocabulary is loaded
- **THEN** it SHALL define search labels for the language codes `nl`, `en`, `es`, `pt`, `de`, `uk`, and `ru`

#### Scenario: Canonical niche remains the stable identity
- **WHEN** a localized search label is used to construct a search query
- **THEN** the pipeline SHALL still retain the canonical niche key as the lead's niche identity for normalization, scoring, deduplication, and export

### Requirement: Localized search vocabulary supports fallback behavior
The localized search vocabulary SHALL allow the pipeline to fall back to a canonical search label when a requested niche-language translation is missing.

#### Scenario: Missing localized phrase falls back to canonical label
- **WHEN** a config requests a `search_language` for which a niche has no localized phrase
- **THEN** the pipeline SHALL use the canonical niche label rather than failing the run
