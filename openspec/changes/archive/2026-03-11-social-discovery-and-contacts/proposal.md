## Why

The current pipeline discovers leads exclusively via OSM/Overpass (and optionally Google Places) and uses Instagram/Facebook only as *enrichment signals* on already-discovered businesses. This means any SMB that lacks an OSM entry is invisible to the system — even if it has a visible Instagram or Facebook presence with full contact details. Adding social-native discovery and a structured contact extraction layer multiplies reachable leads and improves outreach quality by surfacing emails, booking links, phones, and messaging handles that currently get dropped.

## What Changes

- **New**: `InstagramDiscoveryCollector` — discovers business candidates by searching Instagram profiles for niche + city keywords; emits normalized `SocialCandidate` payloads independently of any OSM/Places match.
- **New**: `FacebookDiscoveryCollector` — discovers business candidates via Facebook Pages search; same interface as Instagram collector.
- **New**: `SocialCandidate` model — lightweight intermediate entity for leads sourced from social platforms before cross-source matching.
- **New**: `CrossSourceMatcher` — matches `SocialCandidate` entities against existing `BusinessLead` records using name similarity, city, phone, website domain, and social URL overlap; assigns confidence (`HIGH / MEDIUM / LOW / UNMATCHED`).
- **New**: `ContactDiscovery` enrichment module — accepts a business entity + known URLs + social data; extracts all public emails, phones, WhatsApp/Messenger/Telegram links, booking links, contact forms, Linktree hubs; deduplicates; selects primary contacts per type.
- **New**: `ContactabilityScorer` — adds a `contactability_score` (0–100) derived from contact channel availability and confidence.
- **Extended**: `lead-discovery` pipeline step — ingests candidates from Google/OSM *and* Instagram *and* Facebook; unifies them via matcher before scoring.
- **Extended**: `lead-scoring` — includes `contactability_score` in final score with a small weight; adds `match_confidence` field.
- **Extended**: `BusinessLead` model + exports — adds `lead_source`, `source_platforms`, `all_emails`, `all_phones`, `primary_email`, `primary_phone`, `primary_contact_method`, `whatsapp_links`, `messenger_links`, `booking_links`, `contact_form_urls`, `contactability_score`, `match_confidence`.
- **Feature flags**: `enable_social_discovery` and `enable_contact_discovery` in run config; both default `false` so existing runs are unaffected.

## Capabilities

### New Capabilities
- `social-discovery`: Instagram and Facebook as first-class lead discovery sources; SocialCandidate model; cross-source matching; lead preservation for unmatched social leads.
- `contact-discovery`: Structured extraction, normalization, deduplication, and primary-selection of all publicly available contact data for each business.

### Modified Capabilities
- `lead-discovery`: Pipeline step now accepts candidates from three sources (OSM/Places, Instagram, Facebook) and performs cross-source matching before passing unified leads downstream.
- `lead-scoring`: `contactability_score` added as a new sub-score; `match_confidence` recorded alongside tier; score formula extended with a small `contactability` weight.

## Impact

- `src/collectors/` — two new files (`instagram_discovery_collector.py`, `facebook_discovery_collector.py`); `social_collector.py` extended with contact-extraction helpers.
- `src/enrichment/` — new `contact_discovery.py`; new `cross_source_matcher.py`.
- `src/scoring/` — new `contactability.py`.
- `src/models.py` — `BusinessLead` fields extended; new `SocialCandidate` dataclass added.
- `src/enums.py` — new enums: `ContactType`, `ContactCategory`, `LeadSourceType`, `MatchConfidence`.
- `run_europe_smb.py` — new pipeline stages wired under feature flags; config keys added.
- `config/run_europe_smb.json` — two new optional boolean flags.
- `viewer/app.py` — new contact-info section in detail panel; `contactability_score` in scores column.
- No database / Alembic changes needed — project stores leads as JSON/CSV flat files, not a relational DB.
- No breaking changes to existing fields or exports; all additions are additive.
