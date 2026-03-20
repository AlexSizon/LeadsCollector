# Europe SMB Lead Agent

AI-powered pipeline that discovers, audits, and scores SMB businesses in Europe as leads for web development, CRO, and local SEO services.

## What it does

1. **Discovers** local businesses (dentists, barbershops, beauty salons, etc.) via Google Places API for each niche × city combination
2. **Enriches** records by normalising phone numbers, extracting root domains, and classifying website presence
3. **Audits** websites for technical health, SEO basics, and UX/CRO signals
4. **Analyses** Instagram presence as a business-maturity indicator
5. **Scores** each lead on four dimensions and produces a final `lead_priority_score`
6. **Generates** evidence-based outreach angles and short pitches
7. **Deduplicates** businesses across all queries before output

## Output format

A JSON array of lead objects. Example:

```json
{
  "company_name": "Smile Studio Berlin",
  "niche": "dentist",
  "country": "Germany",
  "city": "Berlin",
  "google_rating": 4.8,
  "google_reviews_count": 214,
  "website_status": "HAS_WEBSITE",
  "instagram_status": "FOUND_ACTIVE_WITH_LINK",
  "business_strength_score": 87.0,
  "website_problem_score": 71.0,
  "commercial_opportunity_score": 82.0,
  "instagram_signal_score": 80.0,
  "lead_priority_score": 79.5,
  "tier": 1,
  "issues_found": ["No visible CTA", "Missing meta description"],
  "improvement_opportunities": ["Add booking CTA", "Write meta descriptions"],
  "outreach_angle": "Strong review profile (214 reviews) but weak conversion infrastructure.",
  "short_pitch": "You already have strong local demand and social proof. A mobile-first booking flow could convert more visitors into appointments."
}
```

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Set API key

```bash
export GOOGLE_PLACES_API_KEY="your_api_key_here"
```

### 3. Configure input

Edit `config/markets.json` to set your target markets:

```json
{
  "countries": ["Germany", "Spain", "Netherlands"],
  "cities": ["Berlin", "Munich", "Madrid", "Barcelona", "Amsterdam"],
  "niches": ["dentist", "barbershop", "beauty salon"],
  "search_languages": ["en", "de", "es", "nl"],
  "language_priority": ["en", "de", "es", "nl"],
  "max_results_per_query": 50,
  "min_reviews_threshold": 20,
  "min_rating_threshold": 4.0,
  "include_instagram_analysis": true,
  "run_website_audit": true,
  "output_format": "json"
}
```

Bundled presets are also available when you want a ready-to-run campaign without hand-editing the market list. For Ukraine-focused website sales outreach, use `config/run_ukraine_smb.json`.

`search_languages` controls which languages the pipeline uses to form discovery queries. `language_priority` still controls response/detail language where the upstream source supports it. Supported search languages are `nl`, `en`, `es`, `pt`, `de`, `uk`, and `ru`. If `search_languages` is omitted, the pipeline stays backward compatible and searches with the canonical niche labels from `niches`.

The Ukraine preset targets `Kyiv`, `Lviv`, `Kharkiv`, `Odesa`, and `Ivano-Frankivsk` and intentionally limits niches to categories that both:
- map cleanly to the current Overpass fallback collector
- have strong website-improvement demand such as booking, menus, local SEO, catalog pages, and better contact flows

The curated Ukraine niche set is:
- `beauty salon`
- `restaurant`
- `bakery`
- `florist`
- `boutique`
- `cosmetics shop`
- `pet shop`
- `home decor shop`

The bundled Ukraine presets now search each niche in `en`, `uk`, and `ru` via `search_languages: ["en", "uk", "ru"]` while keeping `language_priority` tuned for Ukrainian-first responses.

### 4. Run the pipeline

**JSON output to file:**
```bash
python -m src.main --config config/markets.json --output data/leads.json
```

**Ukraine preset with the OSM-first runner:**
```bash
python run_europe_smb.py --config config/run_ukraine_smb.json
```

**Ukraine validation run capped at about 100 raw leads before deduplication:**
```bash
python run_europe_smb.py --config config/run_ukraine_smb_test_100.json
```

**CSV output to file:**
```bash
python -m src.main --config config/markets.json --output data/leads.csv --format csv
```

**JSON to stdout:**
```bash
python -m src.main --config config/markets.json --output -
```

Each run now produces two log formats under `logs/`:
- `pipeline_<run_id>.jsonl`: structured event log for analysis and automation
- `terminal_<run_id>.log`: human-readable terminal transcript with per-step progress messages

The terminal progress stream is mirrored into the transcript automatically, so you do not need to wrap commands with `tee`.

Terminal transcripts now support verbosity modes:
- `normal` (default): operator-first output with query progress, anomalies, dedup/export, and summary lines
- `verbose`: detailed per-lead stage tracing in addition to the operator summary lines
- `debug`: reserved for deeper diagnostics

You can select verbosity per run:

```bash
python -m src.main --config config/markets.json --output data/leads.json --terminal-verbosity verbose
python run_europe_smb.py --config config/log_test_200.json --terminal-verbosity normal
```

You can also set defaults in config files:

```json
{
  "terminal_verbosity": "normal",
  "terminal_summary_every_queries": 5
}
```

In `normal` mode, the transcript favors operator readability and emits city/final summaries, retry-aware query outcomes, and anomaly lines such as zero-result queries or unexpected website states.

For long OSM-based runs, expect occasional Overpass retries and possible Google Search `429` responses from the optional social-discovery collectors. The core OSM discovery, website audit, contact discovery, scoring, deduplication, and export pipeline can still complete successfully, but social enrichment may be partial when Google throttles search requests.

### 5. Run tests

```bash
python -m pytest tests/ -v
```

## Project structure

```
config/
  markets.json         # Input configuration
  niches.json          # Niche vocabulary and weights
  scoring_rules.json   # Scoring weights and thresholds

src/
  main.py              # CLI entry point
  pipeline.py          # Stage orchestrator
  models.py            # Pydantic + dataclass models
  enums.py             # WebsiteStatus, InstagramStatus enums

  collectors/
    google_places_collector.py   # Google Places API
    website_collector.py         # Website presence + HTTP checks
    instagram_signal_collector.py # Instagram signal heuristics

  enrichment/
    normalizer.py        # Phone, name, domain normalisation
    deduplicator.py      # Cross-query deduplication
    domain_resolver.py   # Root domain extraction + social detection

  auditors/
    technical_auditor.py # HTTPS, SSL, viewport, redirects
    seo_auditor.py       # Title, meta, H1, schema, local SEO
    ux_auditor.py        # CTA, tel:, forms, reviews

  scoring/
    business_strength.py      # Reviews + rating score
    website_problem.py        # Website gap severity score
    commercial_opportunity.py # Commercial upside score
    instagram_signal.py       # Instagram maturity score
    final_score.py            # Weighted final score + tier

  output/
    exporter_json.py   # JSON array export
    exporter_csv.py    # CSV flat export

  prompts/
    system_prompt.txt  # Agent system instructions
    outreach_prompt.txt # Task prompt template

data/          # Output leads (gitignored)
logs/          # Run logs (gitignored)
tests/         # Unit and smoke tests
```

## Scoring formula

```
lead_priority_score =
  0.30 × business_strength_score
  + 0.35 × website_problem_score
  + 0.25 × commercial_opportunity_score
  + 0.10 × instagram_signal_score
```

## Lead tiers

| Tier | Description |
|------|-------------|
| 1 | Strong business (strength ≥ 65), no or broken website |
| 2 | Good business (priority ≥ 55) with specific website gaps |
| 3 | Average business (priority ≥ 35) with some issues |
| 4 | Low priority — insufficient data or low activity |

## Tuning scoring weights

Edit `config/scoring_rules.json` to adjust weights, niche bonuses, city attractiveness multipliers, and tier thresholds. The file is self-documenting.
