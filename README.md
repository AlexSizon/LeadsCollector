# Europe SMB Lead Agent

AI-powered pipeline that discovers, audits, and scores SMB businesses in Europe as leads for web development, CRO, and local SEO services.

## What it does

1. **Discovers** local businesses (dentists, barbershops, beauty salons, etc.) via Google Places API for each niche × city combination
2. **Enriches** records by normalising phone numbers, extracting root domains, and classifying website presence
3. **Audits** websites for technical health, SEO basics, and UX/CRO signals
4. **Analyses** Instagram presence as a business-maturity indicator
5. **Scores** each lead on four dimensions and produces a final `lead_priority_score`
6. **Generates** evidence-based outreach angles and short pitches
7. **Classifies** email-first outreach eligibility with provenance and policy reasons
8. **Deduplicates** businesses across all queries before output

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
  "short_pitch": "You already have strong local demand and social proof. A mobile-first booking flow could convert more visitors into appointments.",
  "contact_provenance": {
    "email": "scraped"
  },
  "email_eligibility": "allowed",
  "email_eligibility_reason": "scraped business email available",
  "outreach_policy_decision": "allowed",
  "outreach_policy_reason": "scraped email allowed by policy",
  "outreach_policy_version": "strict-email-first-v1",
  "offer_type": "website-improvement",
  "email_subject": "Smile Studio Berlin: ideas to improve the current site",
  "email_opening": "I noticed a few website issues that could make it harder for customers to contact or book with Smile Studio Berlin.",
  "email_cta": "If useful, I can point out the top website fixes worth making first.",
  "email_body_preview": "I noticed a few website issues that could make it harder for customers to contact or book with Smile Studio Berlin. You already have strong local demand and social proof. A mobile-first booking flow could convert more visitors into appointments. If useful, I can point out the top website fixes worth making first."
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
  "language_priority": ["en", "de", "es", "nl"],
  "max_results_per_query": 50,
  "min_reviews_threshold": 20,
  "min_rating_threshold": 4.0,
  "include_instagram_analysis": true,
  "run_website_audit": true,
  "output_format": "json"
}
```

### 4. Run the pipeline

**JSON output to file:**
```bash
python -m src.main --config config/markets.json --output data/leads.json
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
  "terminal_summary_every_queries": 5,
  "outreach_policy_path": "config/outreach_policy.json",
  "outreach_store_path": "data/outreach.db",
  "outreach_export_dir": "output/outreach_campaigns",
  "outreach_execution_mode": "export-only",
  "outreach_daily_send_limit": 50,
  "outreach_policy_version": "strict-email-first-v1",
  "outreach_sender_profile": {
    "profile_name": "default",
    "from_email": "sales@example.com",
    "reply_to": "sales@example.com",
    "from_name": "Alex",
    "mode": "export-only"
  }
}
```

In `normal` mode, the transcript favors operator readability and emits city/final summaries, retry-aware query outcomes, and anomaly lines such as zero-result queries or unexpected website states.

### 4a. Email-first outreach workflow

The pipeline now enriches each lead with sendability-oriented fields:
- `contact_provenance`
- `email_eligibility` and `email_eligibility_reason`
- `outreach_policy_decision`, `outreach_policy_reason`, `outreach_policy_version`
- `offer_type`, `email_subject`, `email_opening`, `email_cta`, `email_body_preview`

Mutable outreach operations live in a local SQLite store:
- default path: `data/outreach.db`
- export batches: `output/outreach_campaigns/`

The Streamlit viewer exposes an outreach workspace backed by that store for draft review, approval, campaign batching, export, and feedback updates.

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

  outreach/
    policy.py          # Provenance + eligibility policy rules
    generation.py      # Email-first draft field generation
    store.py           # SQLite campaign/suppression state
    workflow.py        # Draft, approval, export, and feedback helpers

  prompts/
    system_prompt.txt  # Agent system instructions
    outreach_prompt.txt # Task prompt template

data/          # Output leads (gitignored)
data/outreach.db # Local outreach campaign store
logs/          # Run logs (gitignored)
tests/         # Unit and smoke tests
```

## Operator prerequisites for real sending

Before enabling `direct-send`, you still need to provide and own:
- a sender mailbox or ESP account
- SMTP credentials or an ESP API integration
- `SPF`, `DKIM`, and ideally `DMARC` for the sender domain
- sender identity details: display name, from address, reply-to, and landing page/site
- offer packaging: what you are selling, pricing approach, and CTA destination
- compliance choices: allowed countries, guessed-email policy, and suppression owner
- operating rules: daily send cap, approval owner, and bounce/opt-out handling process

Without that setup, the safe default mode is `export-only`.

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
