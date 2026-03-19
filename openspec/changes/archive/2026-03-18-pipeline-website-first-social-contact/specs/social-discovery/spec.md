## ADDED Requirements

### Requirement: Website HTML is the primary source for social link discovery
The system SHALL, when a lead has `website_status == HAS_WEBSITE`, call `SocialCollector.extract_from_html(html, base_url)` on the already-fetched website response as the first social discovery step. The results SHALL be applied to the corresponding social URL fields on `BusinessLead` (`instagram_url`, `facebook_url`, `tiktok_url`, `linkedin_url`, `youtube_url`, `pinterest_url`, `whatsapp_url`, `telegram_url`) before any search-based discovery is attempted.

#### Scenario: Instagram URL extracted from website HTML and stored on lead
- **WHEN** `SocialCollector.extract_from_html()` finds a link to `instagram.com/<handle>` in the business website HTML
- **THEN** `lead.instagram_url` SHALL be set to that URL and `lead.instagram_presence_status` SHALL be set to `FOUND_ON_WEBSITE`

#### Scenario: Facebook URL extracted from website HTML and stored on lead
- **WHEN** `SocialCollector.extract_from_html()` finds a link to `facebook.com/<page>` or `m.facebook.com/<page>` in the business website HTML
- **THEN** `lead.facebook_url` SHALL be set to that URL and `lead.facebook_presence_status` SHALL be set to `FOUND_ON_WEBSITE`

#### Scenario: Multiple social platforms extracted in one pass
- **WHEN** the website HTML contains social links for Instagram, LinkedIn, and Facebook
- **THEN** all three SHALL be extracted and stored on the lead in a single `SocialCollector.extract_from_html()` call

#### Scenario: Social extraction skipped for leads without a working website
- **WHEN** `lead.website_status` is `NO_WEBSITE`, `BROKEN_WEBSITE`, or `SOCIAL_ONLY`
- **THEN** `SocialCollector.extract_from_html()` SHALL NOT be called for that lead in Stage 3

#### Scenario: Website HTML extraction does not replace an existing non-null social URL
- **WHEN** `lead.instagram_url` is already set (from a prior source) and `SocialCollector` finds a different Instagram URL
- **THEN** `lead.instagram_url` SHALL remain unchanged (fill-if-empty semantics)

### Requirement: Linktree and link hub pages are resolved to surface nested social links
The system SHALL, when `enable_linktree_resolution` is `true` (default: `true`), detect if any extracted social URL or the website URL itself points to a known link-hub domain (`linktr.ee`, `beacons.ai`, `bio.site`, `solo.to`, `taplink.cc`). If so, the system SHALL make one additional GET request (timeout ≤ 5s) to that hub URL, run `SocialCollector.extract_from_html()` on the hub response, and apply any newly discovered social URLs to the lead that are not already set.

#### Scenario: Linktree URL found in website HTML triggers hub resolution
- **WHEN** `SocialCollector.extract_from_html()` returns a social URL pointing to `linktr.ee/<handle>`
- **THEN** the pipeline SHALL fetch that Linktree page and run social extraction on its HTML content

#### Scenario: Hub resolution discovers Instagram URL not found on main page
- **WHEN** the main website links to a Linktree page, and the Linktree page contains an instagram.com link
- **THEN** `lead.instagram_url` SHALL be set to that Instagram URL and `lead.instagram_presence_status` SHALL be set to `FOUND_VIA_HUB`

#### Scenario: Hub resolution limited to one follow-up fetch per lead
- **WHEN** a lead's hub page also links to another hub
- **THEN** the pipeline SHALL NOT fetch the second-level hub; resolution stops after one follow-up fetch

#### Scenario: Hub resolution skipped when flag is false
- **WHEN** `enable_linktree_resolution` is `false` in config
- **THEN** no hub pages SHALL be fetched and hub-domain URLs SHALL be stored as-is (the hub URL itself is preserved)

#### Scenario: Hub fetch failure does not block pipeline
- **WHEN** the hub page fetch returns an error (network timeout, 4xx, 5xx)
- **THEN** a debug warning SHALL be logged and the pipeline SHALL continue without the hub social links

### Requirement: Search-based social discovery runs only for leads with no website-sourced social presence
The system SHALL, in Stage 5b, skip `InstagramDiscoveryCollector` enrichment for any individual lead that already has a non-null `instagram_url` (set via website HTML, JSON-LD, or hub resolution). Likewise, `FacebookDiscoveryCollector` enrichment SHALL be skipped for any lead that already has a non-null `facebook_url`. Search-based discovery continues to run at the niche × city level to discover social-first candidates (businesses only present on social platforms) regardless of existing leads' social status.

#### Scenario: Instagram search enrichment skipped when instagram_url already set
- **WHEN** `lead.instagram_url` is non-null before Stage 5b runs
- **THEN** that specific lead SHALL NOT be updated from `InstagramDiscoveryCollector` search results; it SHALL retain its existing `instagram_url` and `instagram_presence_status`

#### Scenario: Facebook search enrichment skipped when facebook_url already set
- **WHEN** `lead.facebook_url` is non-null before Stage 5b runs
- **THEN** that specific lead SHALL NOT be updated from `FacebookDiscoveryCollector` search results for Facebook URL enrichment

#### Scenario: Search discovery still runs for niche × city to find social-first candidates
- **WHEN** `enable_social_discovery` is `true`
- **THEN** `InstagramDiscoveryCollector.search()` and `FacebookDiscoveryCollector.search()` SHALL still be called per niche × city combination to discover new businesses that may only appear on social platforms

#### Scenario: Unresolved lead gets instagram_presence_status NOT_FOUND after all sources exhausted
- **WHEN** a lead with a website has gone through website HTML extraction, JSON-LD extraction, hub resolution, and search-based matching — and `instagram_url` is still null
- **THEN** `lead.instagram_presence_status` SHALL be set to `SocialPresenceStatus.NOT_FOUND`

## MODIFIED Requirements

### Requirement: Discover Instagram business candidates for a niche × city query
The system SHALL, when `enable_social_discovery` is `true`, query publicly accessible Instagram pages to find business candidate profiles matching a given niche and city, and return a list of `SocialCandidate` objects. When a `SocialCandidate` with `source_platform="instagram"` is merged into a `BusinessLead`, the candidate's Instagram URL SHALL be stored in `lead.instagram_url` (not silently dropped) and `lead.instagram_presence_status` SHALL be set to `FOUND_VIA_SEARCH`. This search path is the fallback layer — it is intended for discovering social-first candidates and for enriching leads whose website-based extraction already ran but yielded no Instagram presence. For leads where `instagram_url` is already set from website or JSON-LD extraction, this search result SHALL NOT overwrite the existing URL.

#### Scenario: Discovery returns normalised candidates
- **WHEN** `InstagramDiscoveryCollector.search(niche="restaurant", city="Madrid", country="Spain")` is called
- **THEN** the collector SHALL return a list of `SocialCandidate` objects with at least `source_platform="instagram"`, `display_name`, `city`, and `niche` populated from the found profiles

#### Scenario: Instagram URL stored on merged lead when lead had no prior instagram_url
- **WHEN** `CrossSourceMatcher.merge_into(candidate, lead)` is called with a candidate whose `social_urls["instagram"]` is non-null AND `lead.instagram_url` is currently `None`
- **THEN** `lead.instagram_url` SHALL be set to that URL and `lead.instagram_presence_status` SHALL be set to `FOUND_VIA_SEARCH`

#### Scenario: Instagram URL NOT overwritten when lead already has instagram_url from website extraction
- **WHEN** `CrossSourceMatcher.merge_into(candidate, lead)` is called AND `lead.instagram_url` is already non-null (set from `FOUND_ON_WEBSITE` or `FOUND_IN_SCHEMA`)
- **THEN** `lead.instagram_url` SHALL remain unchanged and `lead.instagram_presence_status` SHALL NOT be downgraded to `FOUND_VIA_SEARCH`

#### Scenario: Instagram URL stored on stub lead created from unmatched candidate
- **WHEN** a `SocialCandidate` with `source_platform="instagram"` is promoted to a stub `BusinessLead`
- **THEN** `lead.instagram_url` SHALL be populated from `candidate.social_urls["instagram"]` and `lead.instagram_presence_status` SHALL be set to `FOUND_VIA_SEARCH`

#### Scenario: Graceful empty result when platform is unreachable
- **WHEN** the underlying HTTP request to Instagram fails with a network error or 4xx/5xx response
- **THEN** the collector SHALL log a warning and return an empty list without raising an exception

#### Scenario: Respects configured request delay
- **WHEN** `social_request_delay` is set in config
- **THEN** the collector SHALL pause for at least that many seconds between HTTP requests to Instagram

### Requirement: Discover Facebook business candidates for a niche × city query
The system SHALL, when `enable_social_discovery` is `true`, query publicly accessible Facebook Pages search to find business candidate pages matching a given niche and city, and return a list of `SocialCandidate` objects. When a `SocialCandidate` with `source_platform="facebook"` is merged into a `BusinessLead`, the candidate's website URL and phone SHALL be stored on the lead if those fields were previously empty. The candidate's Facebook URL SHALL be stored in `lead.facebook_url` (if not already set) and `lead.facebook_presence_status` SHALL be set to `FOUND_VIA_SEARCH`. This search path is the fallback layer — for leads where `facebook_url` is already set from website or JSON-LD extraction, this search result SHALL NOT overwrite the existing URL.

#### Scenario: Discovery returns normalised candidates
- **WHEN** `FacebookDiscoveryCollector.search(niche="beauty salon", city="Amsterdam", country="Netherlands")` is called
- **THEN** the collector SHALL return a list of `SocialCandidate` objects with `source_platform="facebook"`, `display_name`, and at least one of: `phone`, `email`, `website_url`, `social_urls`

#### Scenario: Facebook URL stored on merged lead when lead had no prior facebook_url
- **WHEN** `CrossSourceMatcher.merge_into(candidate, lead)` is called with a candidate whose `social_urls["facebook"]` is non-null AND `lead.facebook_url` is currently `None`
- **THEN** `lead.facebook_url` SHALL be set to that URL and `lead.facebook_presence_status` SHALL be set to `FOUND_VIA_SEARCH`

#### Scenario: Facebook URL NOT overwritten when lead already has facebook_url from website extraction
- **WHEN** `CrossSourceMatcher.merge_into(candidate, lead)` is called AND `lead.facebook_url` is already non-null
- **THEN** `lead.facebook_url` SHALL remain unchanged and `lead.facebook_presence_status` SHALL NOT be downgraded to `FOUND_VIA_SEARCH`

#### Scenario: Graceful empty result when platform is unreachable
- **WHEN** any HTTP request to Facebook fails
- **THEN** the collector SHALL return an empty list and log a warning; the pipeline SHALL continue unaffected
