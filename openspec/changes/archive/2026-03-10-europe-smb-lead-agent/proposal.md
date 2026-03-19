## Why

European SMBs (dentists, barbershops, beauty salons, etc.) often lack a proper web presence or have weak websites that fail to convert local demand into appointments and enquiries. There is a clear commercial opportunity to systematically discover, evaluate, and prioritise these businesses as leads for web development, conversion optimisation, and local SEO services — but no automated pipeline currently exists to do this at scale.

## What Changes

- **New**: Configurable pipeline that discovers SMB businesses across European countries, cities, and niches via Google Places API
- **New**: Business enrichment and normalisation layer (phone, domain, category, SMB classification)
- **New**: Website presence detection with a typed status enum (`NO_WEBSITE`, `SOCIAL_ONLY`, `BROKEN_WEBSITE`, `HAS_WEBSITE`, `UNKNOWN`)
- **New**: Multi-dimensional website audit covering technical health, SEO basics, UX/CRO signals, and design quality heuristics
- **New**: Instagram signal analysis used as a business-maturity enrichment layer (not a primary source)
- **New**: Four-component lead scoring model producing a weighted `lead_priority_score`
- **New**: Evidence-based outreach angle and short pitch generation per lead
- **New**: Deduplication logic keyed on `place_id`, root domain, normalised phone, and name+city confidence
- **New**: Structured JSON output conforming to a defined schema with `UNKNOWN` for all uncertain fields

## Capabilities

### New Capabilities

- `lead-discovery`: Find SMB businesses via Google Places API for each niche × city combination, applying configurable filters (min reviews, min rating, business status)
- `business-enrichment`: Normalise and enrich collected business records — phone format, root domain extraction, category vocabulary, social link detection, SMB classification
- `website-audit`: Detect website presence and, when a site exists, audit it across four dimensions: technical, SEO, UX/CRO, and design quality heuristics
- `instagram-signal`: Detect and classify Instagram presence as a business-maturity signal; produce a typed `instagram_status` and numeric `instagram_signal_score`
- `lead-scoring`: Compute four sub-scores (business strength, website problem, commercial opportunity, Instagram signal) and combine them into a final `lead_priority_score` with tier classification
- `outreach-generation`: Generate a concise, evidence-based `outreach_angle` and `short_pitch` for each qualified lead using only observed signals
- `deduplication`: Identify and merge duplicate business records across collection runs using multiple identity keys

### Modified Capabilities

## Impact

- **src/**: All existing source modules (`pipeline.py`, `models.py`, `enums.py`, `collectors/`, `enrichment/`, `scoring/`) are in scope for modification or replacement
- **config/markets.json**: Extended to support the full input config format (countries, cities, niches, thresholds, flags)
- **New directories**: `src/auditors/`, `src/prompts/`, `src/output/`, `data/`, `logs/`, `tests/`
- **External dependencies**: Google Places API key required; Instagram analysis uses public signal heuristics (no private API)
- **Output**: JSON array conforming to the defined result schema; optional CSV export
