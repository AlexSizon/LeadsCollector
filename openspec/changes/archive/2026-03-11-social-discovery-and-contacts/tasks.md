## 1. Models and Enums

- [x] 1.1 Add `ContactType`, `ContactCategory`, `LeadSourceType`, `MatchConfidence` enums to `src/enums.py`
- [x] 1.2 Add `SocialCandidate` dataclass to `src/models.py` (fields: `source_platform`, `handle_or_page_id`, `display_name`, `city`, `country`, `niche`, `website_url`, `phone`, `email`, `social_urls`, `raw_bio`)
- [x] 1.3 Add `MatchResult` dataclass to `src/models.py` (fields: `confidence: MatchConfidence`, `matched_index: Optional[int]`)
- [x] 1.4 Add `ContactResult` dataclass to `src/models.py` (fields: `primary_email`, `all_emails`, `primary_phone`, `all_phones`, `whatsapp_links`, `messenger_links`, `booking_links`, `contact_form_urls`, `primary_contact_method`)
- [x] 1.5 Extend `BusinessLead` dataclass with new fields: `lead_source`, `source_platforms`, `match_confidence`, `primary_email`, `all_emails`, `primary_phone`, `all_phones`, `whatsapp_links`, `messenger_links`, `booking_links`, `contact_form_urls`, `primary_contact_method`, `contactability_score`
- [x] 1.6 Update `BusinessLead.to_json()` to include all new fields

## 2. Cross-Source Matcher

- [x] 2.1 Create `src/enrichment/cross_source_matcher.py` with `CrossSourceMatcher` class
- [x] 2.2 Implement `_normalise_name(name: str) -> str` helper (lowercase, strip punctuation, collapse whitespace)
- [x] 2.3 Implement `_name_similarity(a: str, b: str) -> float` using difflib `SequenceMatcher`
- [x] 2.4 Implement `_extract_domain(url: str) -> Optional[str]` helper
- [x] 2.5 Implement `match(candidate: SocialCandidate, leads: List[BusinessLead]) -> MatchResult` with HIGH/MEDIUM/LOW/UNMATCHED logic per design D3
- [x] 2.6 Implement `merge_into(candidate: SocialCandidate, lead: BusinessLead) -> None` — fills empty social fields without overwriting existing values

## 3. Instagram Discovery Collector

- [x] 3.1 Create `src/collectors/instagram_discovery_collector.py` with `InstagramDiscoveryCollector` class
- [x] 3.2 Implement `search(niche: str, city: str, country: str, max_results: int) -> List[SocialCandidate]` using Google site-search for `site:instagram.com "<niche>" "<city>"` as primary source
- [x] 3.3 Add HTML parsing to extract Instagram handle, display name, bio snippet from Google search result snippets
- [x] 3.4 Attempt to fetch the top Instagram profile URLs and extract bio/contact info (phone, email, website link) with configurable `social_request_delay`
- [x] 3.5 Implement exponential backoff (identical pattern to `OverpassCollector`) for HTTP errors
- [x] 3.6 Return empty list on any unrecoverable error; log warning with platform + query info

## 4. Facebook Discovery Collector

- [x] 4.1 Create `src/collectors/facebook_discovery_collector.py` with `FacebookDiscoveryCollector` class
- [x] 4.2 Implement `search(niche: str, city: str, country: str, max_results: int) -> List[SocialCandidate]` using Google site-search for `site:facebook.com "<niche>" "<city>"` as primary source
- [x] 4.3 Add HTML parsing to extract page name, category hint, about snippet from Google search results
- [x] 4.4 Attempt to fetch top Facebook page URLs and extract visible phone, email, website from the public page source with `social_request_delay`
- [x] 4.5 Implement exponential backoff for HTTP errors
- [x] 4.6 Return empty list on any unrecoverable error; log warning

## 5. Contact Discovery Module

- [x] 5.1 Create `src/enrichment/contact_discovery.py` with `ContactDiscovery` class
- [x] 5.2 Implement `extract(lead: BusinessLead, website_response: Optional[Response]) -> ContactResult`
- [x] 5.3 Add extraction of WhatsApp links (`wa.me/`, `api.whatsapp.com/send`) from HTML
- [x] 5.4 Add extraction of Messenger links (`m.me/`, `messenger.com/t/`) from HTML
- [x] 5.5 Add extraction of booking platform links (OpenTable, TheFork, Booksy, Calendly, Reservio, `/booking`, `/reservations`, `/appointments` paths)
- [x] 5.6 Add extraction of contact form URLs (`/contact`, `/kontakt`, `/contacto`, `/contacte`, `/contact-us`, `/contacte-nous`)
- [x] 5.7 Add second-request logic: if no email found on main page AND contact form URL detected → fetch contact page (timeout 5s) and re-run email extraction
- [x] 5.8 Implement `_normalise_email(email: str) -> str` and `_normalise_phone(phone: str) -> str`
- [x] 5.9 Implement deduplication of all contact lists
- [x] 5.10 Implement `_select_primary_email(emails, lead_source_priority) -> Optional[str]`
- [x] 5.11 Implement `_select_primary_phone(phones, existing_phone) -> Optional[str]`
- [x] 5.12 Implement `_select_primary_contact_method(contact_result, niche) -> str` with booking-heavy niche logic
- [x] 5.13 Populate `BusinessLead` contact fields from `ContactResult` without overwriting existing non-null values

## 6. Contactability Scorer

- [x] 6.1 Create `src/scoring/contactability.py` with `compute_contactability_score(lead: BusinessLead) -> float`
- [x] 6.2 Implement channel-point mapping: email=30, phone=20, booking_link=15, contact_form=10, whatsapp=10, messenger=5, instagram_dm=5, facebook_msg=5 (cap at 100)
- [x] 6.3 Add Instagram DM channel detection: `instagram_status in (FOUND_ACTIVE, FOUND_ACTIVE_WITH_LINK)` → +5 pts

## 7. Updated Scoring Formula

- [x] 7.1 Update `src/scoring/final_score.py` `compute_final_score()` to accept `contactability_score` parameter (default `0.0` for backward compat)
- [x] 7.2 Update formula: `0.30 × business_strength + 0.30 × website_problem + 0.25 × commercial_opportunity + 0.05 × instagram_signal + 0.10 × contactability`

## 8. Pipeline Orchestrator Integration

- [x] 8.1 Add `enable_social_discovery` and `enable_contact_discovery` keys to `config/run_europe_smb.json` (both `false`)
- [x] 8.2 Add `social_request_delay` config key (default `3.0`)
- [x] 8.3 Import `InstagramDiscoveryCollector`, `FacebookDiscoveryCollector`, `CrossSourceMatcher`, `ContactDiscovery`, `compute_contactability_score` in `run_europe_smb.py`
- [x] 8.4 Instantiate collectors and matcher once before the city loop (only when flags are enabled)
- [x] 8.5 Add social discovery stage after OSM collection per niche × city: collect Instagram + Facebook candidates when `enable_social_discovery=true`
- [x] 8.6 Add cross-source matching stage: match candidates against current leads list; merge HIGH matches; promote others to new leads
- [x] 8.7 Set `lead_source` and `source_platforms` on all leads (OSM-originating leads default to `"osm"`)
- [x] 8.8 Add contact discovery stage after Stage 4b (current social/email enrichment): run `ContactDiscovery.extract()` when `enable_contact_discovery=true`, populate all contact fields
- [x] 8.9 Add `compute_contactability_score(lead)` call in Stage 5 scoring, store result on `lead.contactability_score`
- [x] 8.10 Pass `contactability_score` to updated `compute_final_score()`

## 9. Export and Viewer Updates

- [x] 9.1 Verify `BusinessLead.to_json()` includes all new fields (covered by 1.6); spot-check output JSON schema
- [x] 9.2 Update `viewer/app.py` detail panel: add `match_confidence`, `lead_source`, `contactability_score` to the scores column
- [x] 9.3 Update `viewer/app.py` contact section: render `all_emails` as mailto links, `all_phones` as tel links, `booking_links` and `whatsapp_links` as clickable URLs
- [x] 9.4 Add `contactability_score` to `TABLE_COLS` and `column_config` in viewer

## 10. Testing and Validation

- [x] 10.1 Smoke-test `CrossSourceMatcher` with a small handcrafted lead list — verify HIGH/MEDIUM/UNMATCHED cases
- [x] 10.2 Smoke-test `ContactDiscovery.extract()` against a known business website (can use any existing lead's website URL)
- [x] 10.3 Smoke-test `InstagramDiscoveryCollector.search()` with a single niche × city — verify graceful empty result on network error
- [x] 10.4 Smoke-test `FacebookDiscoveryCollector.search()` with a single niche × city — verify graceful empty result on network error
- [x] 10.5 Run full pipeline with `enable_social_discovery=false` and `enable_contact_discovery=false`; confirm output identical to current baseline
- [x] 10.6 Run full pipeline with `enable_contact_discovery=true`; verify `contactability_score` > 0 for leads with emails and booking links
