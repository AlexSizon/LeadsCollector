## Why

The pipeline currently collects leads but leaves most of them with no contactable email or phone — social discovery and contact extraction are implemented but disabled. A lead with no reachable contact is useless for outreach. Enabling and expanding these channels maximises the number of businesses we can actually reach.

## What Changes

- **Enable `enable_social_discovery: true`** — activate Instagram + Facebook discovery (Google site-search) for every niche × city query, enriching coverage beyond OSM
- **Enable `enable_contact_discovery: true`** — activate full HTML contact extraction (email, phone, WhatsApp, booking links, contact forms) for every lead with a website
- **NEW: Email domain guesser** — for leads that have a website domain but no email was found anywhere, probe common patterns (`info@`, `contact@`, `hola@`, `hello@`, `contacto@`) and verify each address is plausible via MX record lookup before storing. No email is ever sent.
- **NEW: TripAdvisor discovery** — Google site-search on `tripadvisor.com` for restaurant/café/bakery niches; TripAdvisor public pages often expose phone numbers and website URLs that are absent from OSM
- **Viewer: Reachable Leads tab** — add a dedicated tab/filter in the Streamlit viewer showing only leads with `contactability_score > 0`, sorted by score, with one-click mailto/tel/WhatsApp links

## Capabilities

### New Capabilities

- `email-guesser`: Domain-pattern email probing + MX record verification for leads with a known website domain but no discovered email
- `tripadvisor-discovery`: TripAdvisor scraper (Google site-search + public page parsing) for hospitality-niche lead discovery and phone enrichment

### Modified Capabilities

- `lead-discovery`: Add TripAdvisor as a third social/directory discovery source alongside Instagram and Facebook; activate `enable_social_discovery` by default
- `contact-discovery`: Activate `enable_contact_discovery` by default; add email-guesser as a post-extraction fallback stage
- `lead-scoring`: Bump `contactability_score` by +10 when email was found via guesser+MX-verified (lower confidence than directly scraped email, but reachable)
- `leads-viewer`: Add "Reachable Leads" tab filtered to `contactability_score > 0`; expose one-click outreach links (mailto, tel, WhatsApp, booking)

## Impact

- `config/run_europe_smb.json` — flags enabled by default
- `src/collectors/tripadvisor_collector.py` — new file
- `src/enrichment/email_guesser.py` — new file
- `run_europe_smb.py` — import + wire new stages
- `viewer/app.py` — new tab + outreach link rendering
- Runtime: +15–30% per lead (extra HTTP requests for guesser + TripAdvisor); controlled via `enable_social_discovery` and `enable_contact_discovery` flags
