## Why

The repository already ships market presets for Western Europe, but there is no ready-to-run configuration for Ukraine. That forces operators to assemble cities, language priorities, and niche lists by hand even though Ukraine is a strong target market for selling new websites, redesigns, booking flows, and local SEO improvements to SMBs.

## What Changes

- Add a bundled Ukraine market preset covering Kyiv, Lviv, Kharkiv, Odesa, and Ivano-Frankivsk.
- Curate a niche set that fits the current Overpass-based discovery stack and has clear website/CRO demand for SMB outreach.
- Document why each selected niche is commercially attractive for website sales or website improvement offers in the Ukrainian market.
- Add preset-specific output paths and run defaults so the configuration can be executed without manual editing.

## Capabilities

### New Capabilities
- `market-presets`: Provide curated, ready-to-run market configuration presets with defined geography, niche selection, language priorities, and output defaults for supported SMB lead-generation campaigns.

### Modified Capabilities

## Impact

- `config/`: Add a Ukraine-specific run configuration JSON preset.
- `config/niches.json`: Reuse existing supported niche definitions and confirm the preset only includes niches that map cleanly to the current collector.
- `README.md`: Optionally document the new preset as an example run target for Eastern Europe / Ukraine.
- Lead operators: Gain a reusable starting point for outbound campaigns focused on website creation, redesign, and local conversion improvements.
