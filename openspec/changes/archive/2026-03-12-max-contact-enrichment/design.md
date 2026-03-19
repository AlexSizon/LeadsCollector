## Context

The social-discovery-and-contacts change delivered full infrastructure for Instagram/Facebook discovery, contact extraction, and contactability scoring — all behind feature flags defaulting to `false`. The current pipeline collects ~3,700 leads per run but the vast majority have no email or phone, making outreach impossible without manual research.

This change activates those flags and adds two supplementary enrichment stages: a domain-pattern email guesser (probe `info@`, `contact@`, etc. with MX verification) and a TripAdvisor collector for hospitality niches (restaurants, bakeries, cafés) where TripAdvisor publicly exposes phone numbers that OSM typically lacks.

Existing code path: OSM discovery → website check → audit → Instagram signal → social extraction → scoring → dedup.
New code path: OSM discovery → **Instagram/FB/TripAdvisor discovery** → cross-source match → website check → audit → Instagram signal → social extraction → **contact discovery** → **email guesser** → scoring → dedup.

## Goals / Non-Goals

**Goals:**
- Maximise the number of leads with at least one reachable contact (email, phone, WhatsApp, booking link)
- Enable `enable_social_discovery` and `enable_contact_discovery` in the default run config
- Add TripAdvisor as a third discovery source for hospitality niches
- Add email domain guesser as a last-resort fallback to recover emails from website domains
- Surface reachable leads prominently in the viewer

**Non-Goals:**
- Sending any email or making any outreach (read-only throughout)
- Paying for API access (Hunter.io, Clearbit, etc.) — all scraping remains public-HTML only
- Social discovery for non-hospitality niches on TripAdvisor (TripAdvisor scope limited to restaurant, bakery, café, bar)
- Verified phone validation (MX-style check exists only for email domain verification)

## Decisions

### D1 — TripAdvisor uses same Google site-search pattern as Instagram/Facebook
`site:tripadvisor.com "<niche>" "<city>"` → parse result snippets for business name, city, phone, website URL.

**Why**: Consistent with existing collectors; no TripAdvisor API required; avoids direct scraping of TripAdvisor (which blocks scrapers) since we hit Google instead.

**Alternative considered**: Direct TripAdvisor search API — rejected (requires account + paid plan).

### D2 — Email guesser uses stdlib DNS MX check only; no email is sent
Patterns tested per domain: `info`, `contact`, `hola`, `hello`, `contacto`, `reservas`, `bookings`, `bonjour`.
MX check: `dns.resolver.resolve(domain, 'MX')` with `dnspython` library. If MX record exists for the domain, the address is stored as `guessed_email` (distinct from `primary_email` to preserve provenance).

**Why**: No email is sent — purely passive. `dnspython` is a lightweight, well-maintained stdlib-style library already used in many Python projects. Avoids false positives from domains with no mail server at all.

**Alternative considered**: `socket.getaddrinfo` MX fallback — insufficient; only resolves A records, not MX. Rejected.

### D3 — Guesser runs only when no email found AND website domain is known
Guard conditions prevent unnecessary DNS queries:
```python
if not lead.primary_email and not lead.all_emails and lead.website_url:
    guessed = email_guesser.guess(lead.website_url, lead.niche)
    if guessed:
        lead.all_emails = [guessed]
        lead.primary_email = guessed
```
**Why**: Limits DNS overhead to ~30% of leads (those with website but no email). Each guess costs ≤5 MX lookups × ~50ms = ≤250ms per qualifying lead.

### D4 — Social discovery enabled by default; TripAdvisor off by default
`config/run_europe_smb.json`:
```json
"enable_social_discovery": true,
"enable_contact_discovery": true,
"enable_email_guesser": true,
"enable_tripadvisor_discovery": false
```
TripAdvisor off by default because it adds significant runtime. Can be enabled per-run via config.

**Why social on by default**: The feature was built to be used; benefit (more leads) outweighs cost (longer runtime).

### D5 — TripAdvisor collector scoped to hospitality niches only
Only triggered for: `restaurant`, `bakery`, `café`, `bar`, `café-bar`.
**Why**: TripAdvisor's data is hospitality-specific. Running it for florist, gift shop, etc. produces irrelevant results.

### D6 — `guessed_email` field added to BusinessLead for provenance tracking
Rather than silently overwriting `primary_email`, store as `guessed_email` (separate field). The viewer can show it with a ⚠️ indicator. Contactability scoring awards +15 pts for verified guessed email (vs +30 for scraped email).

**Why**: Outreach sender needs to know if an email was directly found vs guessed — affects deliverability expectations.

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| Google blocks site-search queries after high volume | Existing backoff logic handles this; `social_request_delay` config key controls pacing. Consider running social discovery in off-peak hours. |
| TripAdvisor changes HTML structure | Guesser falls back to empty list gracefully; no pipeline crash. |
| DNS MX lookups add latency at scale | Only runs when no email found (≈30% of leads); cap at 5 patterns per domain; 250ms worst case per lead. |
| Guessed email false positives (MX exists but mailbox doesn't) | Field labelled `guessed_email`; contactability score reduced (+15 vs +30); outreach user can decide. |
| Runtime increase | Social discovery adds ~1–2h to full run. Separate configs (e.g. `run_europe_smb_social.json`) allow selective runs. |

## Migration Plan

1. Install `dnspython`: `pip install dnspython` → add to `requirements.txt`
2. Enable flags in `config/run_europe_smb.json`
3. Deploy new files (`tripadvisor_collector.py`, `email_guesser.py`)
4. Wire into `run_europe_smb.py`
5. Update viewer for new `guessed_email` field and Reachable tab
6. No data migration needed — new fields default to `None`/`0.0` on existing leads

**Rollback**: Set flags back to `false` in config. All new code paths are guard-checked.

## Open Questions

- Should `guessed_email` be exposed in the CSV export, or only in the viewer? (Recommend: yes, with a `_guessed` suffix column)
- Should TripAdvisor be run in a separate `run_*.py` script to avoid bloating the main run? (Recommend: separate `run_tripadvisor_enrich.py` post-process over existing leads JSON)
