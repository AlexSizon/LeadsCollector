# Verification Report — pipeline-website-first-social-contact

**Date:** 2025-07-19  
**Schema:** spec-driven  
**Change artifacts:** proposal.md ✓ · design.md ✓ · specs (6 files) ✓ · tasks.md ✓  
**Test baseline:** 198/198 passing  

---

## Summary Scorecard

| Dimension | Status | Notes |
|---|---|---|
| **Completeness** | ⚠️ PARTIAL | 63/69 tasks correct; 2 false-positives + 4 genuinely incomplete |
| **Correctness** | ⚠️ GAPS | REQ-CD2 unimplemented; task 8.3 mechanism wrong; task 7.3 missing |
| **Coherence** | ⚠️ DEVIATION | Decision 4 per-lead skip omitted; batch search used instead |

---

## CRITICAL — Requirements Not Met

### C1 · REQ-CD2 — Contact discovery on social-stub leads (Tasks 9.1–9.3)

**Spec:** `specs/contact-discovery/spec.md` — *"Contact extraction runs on social-stub leads with bio-discovered website URLs."*

**Status:** Not implemented.  
Tasks 9.1 (deferred queue), 9.2 (run `ContactDiscovery.extract()` after Stage 5b), 9.3 (run `EmailGuesser` on stubs with no emails) are all marked `[ ]` in `tasks.md`.

**Impact:** Social-stub leads that have a `website_url` (from bio parsing) never receive contact enrichment — no emails or phones are discovered for them. `all_emails` will always be empty for these leads.

**Required fix:** After Stage 5b, collect stub leads with `website_url is not None`, fetch the website, run `ContactDiscovery.extract()` + fill-if-empty `apply_to_lead()`, then run `EmailGuesser` if `all_emails` is still empty.

---

### C2 · Task 8.3 false-positive — `merge_into()` does not set `FOUND_VIA_SEARCH`

**Spec:** `specs/social-presence-tracking/spec.md` — *"When search-sourced URL is merged into an existing lead, presence status is set to `FOUND_VIA_SEARCH`."*

**Status:** Incorrectly marked `[x]` in `tasks.md`. The actual `CrossSourceMatcher.merge_into()` fills social URLs with fill-if-empty semantics but **never updates the lead's `instagram_presence_status` or `facebook_presence_status`**.

**Impact:** When a HIGH-confidence search match fills an existing lead's `instagram_url`, the status remains `UNKNOWN`. The post-Stage-5b sweep checks `not _lead.instagram_url` and skips it (URL is now set), so the status stays `UNKNOWN` permanently — violating the status-tracking contract.

**Required fix:** In `merge_into()`, after each social URL is written to the lead, check `lead.instagram_presence_status` / `lead.facebook_presence_status` — if it is `UNKNOWN` or `NOT_FOUND`, update it to `FOUND_VIA_SEARCH`.

```python
# After the loop in merge_into():
from ..enums import SocialPresenceStatus as _SPS
_downgradable = {_SPS.UNKNOWN, _SPS.NOT_FOUND}
if candidate.social_urls.get("instagram") and not getattr(lead, "instagram_url", None):
    # (URL was just set above)
    if lead.instagram_presence_status in _downgradable:
        lead.instagram_presence_status = _SPS.FOUND_VIA_SEARCH
if candidate.social_urls.get("facebook") and not getattr(lead, "facebook_url", None):
    if lead.facebook_presence_status in _downgradable:
        lead.facebook_presence_status = _SPS.FOUND_VIA_SEARCH
```

---

## SIGNIFICANT — Incorrect Implementation (Marked Done)

### S1 · Task 7.3 false-positive — Overpass leads not tagged `LeadSourceType.OSM`

**Task:** *"Tag resulting leads with `lead_source = LeadSourceType.OSM`"*

**Status:** Incorrectly marked `[x]`. `LeadSourceType` is never imported in `src/pipeline.py`. When `GooglePlaces` fails and `OverpassCollector.search()` is called as fallback, the shared `places` variable is overwritten but the `BusinessLead` is created with no `lead_source` field set — it defaults to whatever the model's default is, not `LeadSourceType.OSM`.

**Verification:** `grep -n "LeadSourceType" src/pipeline.py` → 0 matches.

**Impact:** OSM-sourced leads cannot be identified or filtered after the fact. Downstream analytics and data provenance are incorrect.

**Required fix:** Introduce a boolean flag `_used_overpass` in the fallback block, then set `lead.lead_source = LeadSourceType.OSM` when creating the `BusinessLead`.

---

## COHERENCE — Design Decision Deviation

### D1 · Decision 4 — Per-lead search skip vs. batch niche × city search

**Design decision:** *"In Stage 5b, before calling `InstagramDiscoveryCollector.search()` for a lead's niche × city combination, check if `lead.instagram_url` is already populated; if so, skip the Instagram search for that lead."*

**Implementation:** Stage 5b always runs `_ig_discovery.search(niche, city, country, max_results)` and `_fb_discovery.search(niche, city, country, max_results)` for every niche × city combination regardless of whether any existing leads already have Instagram/Facebook URLs set. The fill-if-empty semantics in `merge_into()` ensure existing URLs are never overwritten, so **data integrity is preserved** — but the API calls are made unnecessarily.

**Impact:** Mild — no data corruption, but potentially wasteful API calls when a niche × city already has fully-enriched leads. The design's stated goal ("skip the search") is not achieved.

**Note:** This deviation is lower priority than C1/C2/S1 since correctness is maintained. Whether to fix depends on API cost sensitivity.

---

## PASSING — Requirements Verified Against Code

| Requirement | Spec | Implementation | Status |
|---|---|---|---|
| REQ-SD1: Website HTML primary social source | social-discovery | `Stage 3b2` → `SocialCollector.extract_from_html()` + `FOUND_ON_WEBSITE` | ✅ |
| REQ-SD2: Linktree hub resolution | social-discovery | `_LINK_HUB_DOMAINS` frozenset + hub fetch + `FOUND_VIA_HUB` | ✅ |
| REQ-SD3: Search-only fallback for leads without website-sourced presence | social-discovery | Stage 5b uses separate `_ig_discovery`/`_fb_discovery` only when existing status is not website-sourced | ✅ |
| REQ-SD4: Instagram business candidates per niche × city | social-discovery | `_ig_discovery.search()` in Stage 5b | ✅ |
| REQ-SD5: Facebook business candidates per niche × city | social-discovery | `_fb_discovery.search()` in Stage 5b | ✅ |
| REQ-JLD1: Extract structured data from JSON-LD | json-ld-extraction | `src/enrichment/json_ld_extractor.py` — `extract_from_html()` | ✅ |
| REQ-JLD2: JSON-LD enriches lead before contact discovery | json-ld-extraction | Step 2 (JSON-LD) runs before Stage 3c (ContactDiscovery) | ✅ |
| REQ-SPT1: `SocialPresenceStatus` enum | social-presence-tracking | `src/enums.py` — 6 values: `FOUND_ON_WEBSITE`, `FOUND_IN_SCHEMA`, `FOUND_VIA_HUB`, `FOUND_VIA_SEARCH`, `NOT_FOUND`, `UNKNOWN` | ✅ |
| REQ-SPT2: Per-platform fields on `BusinessLead` | social-presence-tracking | `instagram_presence_status`, `facebook_presence_status` — both `SocialPresenceStatus`, default `UNKNOWN` | ✅ |
| REQ-SPT3: `social_discovery_method` string field | social-presence-tracking | `lead.social_discovery_method` set to `"website_html"`, `"json_ld"`, `"linktree_hub"`, `"search_fallback"` | ✅ |
| REQ-CD1: JSON-LD feeds contact pool before HTML scraping | contact-discovery | `lead.all_emails.append(jld_email)` occurs in Step 2, before Stage 3c | ✅ |
| REQ-CD2: Contact extraction on social-stub leads | contact-discovery | **NOT IMPLEMENTED** — see C1 | ❌ |
| REQ-CD3: EmailGuesser post-extraction fallback | contact-discovery | `EmailGuesser.guess()` in Stage 3c when `all_emails` is empty | ✅ |
| REQ-LS1: Niche demand weight in business strength | lead-scoring | `niche_weight = self._niche_demand_weights.get(niche, 1.0)` → `compute_business_strength(..., niche_weight=niche_weight)` | ✅ |
| REQ-LS2: `scoring_rules.json` authoritative for weights | lead-scoring | `config/scoring_rules.json` → `final_score_weights` loaded at init; `compute_final_score(..., weights=self._final_score_weights)` | ✅ |
| REQ-EF1: Export presence fields in JSON + CSV | export-format | `instagram_presence_status`, `facebook_presence_status`, `social_discovery_method` in `COLUMNS` + `_flatten_row()` handles `.value`; `to_json()` includes all 3 | ✅ |

---

## Task Progress Accuracy

| Source | Count |
|---|---|
| Tasks marked `[x]` in tasks.md | 65 |
| Tasks actually implemented correctly | **63** |
| False-positives (marked done, not implemented) | **2** (7.3, 8.3) |
| Tasks marked `[ ]` (genuinely incomplete) | 4 (9.1, 9.2, 9.3, 13.6) |
| **True completed tasks** | **63 / 69 (91.3%)** |

---

## Recommended Fix Order

1. **Fix C2 first** — `CrossSourceMatcher.merge_into()` — 5-line change, unblocks correct status tracking for all matched leads.  
2. **Fix S1** — import `LeadSourceType` + tag when Overpass used — ~3-line change.  
3. **Implement C1** — Tasks 9.1–9.3 (deferred contact discovery for social-stubs) — largest remaining work.  
4. **Address D1** (optional) — Add per-lead skip guard before `_ig_discovery.search()` to avoid wasted API calls.  
5. **Task 13.6** — Run live smoke test once real API key is available.

---

## Files Inspected

- [src/pipeline.py](../../../src/pipeline.py) — Stages 3b2, 3c, 5b, post-5b sweep
- [src/enrichment/cross_source_matcher.py](../../../src/enrichment/cross_source_matcher.py) — `merge_into()`
- [src/enrichment/json_ld_extractor.py](../../../src/enrichment/json_ld_extractor.py)
- [src/enrichment/deduplicator.py](../../../src/enrichment/deduplicator.py) — `_merge()`
- [src/enums.py](../../../src/enums.py) — `SocialPresenceStatus`, `LeadSourceType`
- [src/models.py](../../../src/models.py)
- [src/output/exporter_csv.py](../../../src/output/exporter_csv.py)
- [src/scoring/final_score.py](../../../src/scoring/final_score.py)
- [config/scoring_rules.json](../../../config/scoring_rules.json)
- [tasks.md](tasks.md)
- [design.md](design.md)
- All 6 spec files under [specs/](specs/)
