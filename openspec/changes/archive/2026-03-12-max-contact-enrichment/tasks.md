## 1. Model Changes

- [x] 1.1 Add `guessed_email: Optional[str] = None` field to `BusinessLead` dataclass in `src/models.py`
- [x] 1.2 Update `BusinessLead.to_json()` to include `guessed_email`

## 2. Dependency

- [x] 2.1 Add `dnspython` to `requirements.txt` (used by `EmailGuesser` for MX record lookup)

## 3. Email Guesser

- [x] 3.1 Create `src/enrichment/email_guesser.py` with `EmailGuesser` class
- [x] 3.2 Implement `_extract_domain(website_url: str) -> Optional[str]` helper (strip scheme, www., port, path)
- [x] 3.3 Implement `_check_mx(domain: str) -> bool` using `dns.resolver.resolve(domain, "MX")` — return `False` on `NXDOMAIN`, `NoAnswer`, `Timeout`, any exception
- [x] 3.4 Implement `guess(website_url: str, niche: str) -> Optional[str]` — extract domain, call `_check_mx`, probe patterns `["info", "contact", "hola", "hello", "contacto", "reservas", "bonjour", "bookings"]`, return first valid address or `None`
- [x] 3.5 Add niche-aware pattern priority: for `restaurant`/`bakery`/`café` prepend `"reservas"` and `"bookings"` to the probe list
- [x] 3.6 Log debug message on DNS failure; log info when guessed address is found

## 4. TripAdvisor Collector

- [x] 4.1 Create `src/collectors/tripadvisor_collector.py` with `TripAdvisorCollector` class
- [x] 4.2 Define `HOSPITALITY_NICHES = {"restaurant", "café", "café-bar", "bar", "bakery"}` constant
- [x] 4.3 Implement `search(niche: str, city: str, country: str, max_results: int) -> List[SocialCandidate]` — return `[]` immediately if niche not in `HOSPITALITY_NICHES`
- [x] 4.4 Implement Google site-search: `site:tripadvisor.com "<niche>" "<city>"` — parse result titles and URLs
- [x] 4.5 Extract business name and TripAdvisor listing URL from Google search result snippets
- [x] 4.6 Fetch up to 3 TripAdvisor listing pages; extract phone (tel: patterns + visible text regex) and website URL from HTML
- [x] 4.7 Implement exponential backoff (`10s → 20s → 40s`) for HTTP errors — same pattern as existing collectors
- [x] 4.8 Return `[]` on any unrecoverable error; log warning with niche + city info

## 5. Contactability Scorer Update

- [x] 5.1 Update `compute_contactability_score(lead: BusinessLead) -> float` in `src/scoring/contactability.py`: add `+15` pts when `lead.guessed_email` is non-null AND `lead.primary_email` is null (guard: do not stack with the existing scraped-email +30 pts)

## 6. Pipeline Wiring

- [x] 6.1 Set `"enable_social_discovery": true`, `"enable_contact_discovery": true` in `config/run_europe_smb.json`
- [x] 6.2 Add `"enable_tripadvisor_discovery": false`, `"enable_email_guesser": true` to `config/run_europe_smb.json`
- [x] 6.3 Import `TripAdvisorCollector` and `EmailGuesser` in `run_europe_smb.py`
- [x] 6.4 Read `enable_tripadvisor_discovery` and `enable_email_guesser` flags from config in `run_pipeline()`
- [x] 6.5 Instantiate `TripAdvisorCollector` before city loop (guarded by `enable_tripadvisor_discovery`)
- [x] 6.6 Instantiate `EmailGuesser` before city loop (guarded by `enable_email_guesser`)
- [x] 6.7 In Stage 2b (social discovery block): add TripAdvisor search call after Instagram/Facebook, pass candidates to `CrossSourceMatcher` in the same loop
- [x] 6.8 Add Stage 4d (email guesser): after Stage 4c contact discovery, if `enable_email_guesser` and `not lead.primary_email` and `not lead.all_emails` and `lead.website_url` → call `EmailGuesser.guess()` and set `lead.guessed_email`

## 7. Viewer Updates

- [x] 7.1 Wrap existing table/detail view in a "All Leads" tab in `viewer/app.py`; add a "Reachable Leads" tab alongside it (use `st.tabs`)
- [x] 7.2 Implement Reachable Leads tab: filter `contactability_score > 0`, sort descending, show count in tab label; show info message when empty
- [x] 7.3 In Reachable Leads tab table: render `primary_email`/`guessed_email` as `mailto:` link column, `primary_phone` as `tel:` link column, first `whatsapp_links` entry as clickable URL, first `booking_links` entry as clickable URL
- [x] 7.4 In detail panel: when `guessed_email` is non-null and `primary_email` is null, show `⚠️ {guessed_email} (MX verified, not scraped)` instead of plain email text
- [x] 7.5 Update `SCORE_COLS` coercion loop to include `guessed_email` list-column serialisation

## 8. Validation

- [x] 8.1 Smoke-test `EmailGuesser`: use a known domain with MX (e.g. `google.com`) — expect non-None result; use an invalid domain — expect `None`
- [x] 8.2 Smoke-test `TripAdvisorCollector`: verify non-hospitality niche returns `[]` with zero HTTP calls; verify graceful `[]` on network error (mock `requests.Session.get`)
- [x] 8.3 Smoke-test `contactability_score` with `guessed_email` set: verify score = 15 when no other channels; verify score does not double-count with `primary_email`
- [x] 8.4 Run full pipeline with `enable_social_discovery=true`, `enable_contact_discovery=true`, `enable_email_guesser=true`; verify some leads have `guessed_email` and `contactability_score > 0`
- [x] 8.5 Verify Streamlit viewer renders Reachable Leads tab without errors and mailto links are clickable

