## 1. Add Ukraine Preset

- [x] 1.1 Create `config/run_ukraine_smb.json` with `countries`, `cities`, and `city_country_map` for Kyiv, Lviv, Kharkiv, Odesa, and Ivano-Frankivsk
- [x] 1.2 Populate the preset with the curated supported niches: `beauty salon`, `restaurant`, `bakery`, `florist`, `boutique`, `cosmetics shop`, `pet shop`, and `home decor shop`
- [x] 1.3 Set outreach-oriented defaults in the preset for `language_priority`, thresholds, enrichment flags, request delays, terminal verbosity, and dedicated Ukraine output paths

## 2. Verify Preset Compatibility

- [x] 2.1 Confirm every preset niche maps to an existing canonical niche in `src/collectors/overpass_collector.py`
- [x] 2.2 Validate that the preset schema matches the fields consumed by `run_europe_smb.py`
- [x] 2.3 Run a lightweight config validation or smoke execution path to confirm the preset loads without editing

## 3. Document Operator Usage

- [x] 3.1 Add or update operator-facing documentation to mention the Ukraine preset and its intended use for website-sales outreach
- [x] 3.2 Document the rationale for the curated niche list so future changes do not introduce unsupported categories by accident
