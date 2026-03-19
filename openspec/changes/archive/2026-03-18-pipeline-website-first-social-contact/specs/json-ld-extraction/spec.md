## ADDED Requirements

### Requirement: Extract structured business data from JSON-LD blocks in website HTML
The system SHALL, when processing a website response with status `HAS_WEBSITE`, scan all `<script type="application/ld+json">` elements in the HTML and attempt to parse them as schema.org structured data. When a `LocalBusiness` (or subtype) entity is found, the system SHALL extract available fields and return them as a structured dict. This extraction SHALL require no additional HTTP requests — it operates entirely on the already-fetched HTML response.

#### Scenario: LocalBusiness entity found with phone and email
- **WHEN** the website HTML contains a JSON-LD block with `"@type": "LocalBusiness"` (or a recognized subtype) and the block includes `"telephone"` and `"email"` fields
- **THEN** `json_ld_extractor.extract_from_html(html)` SHALL return a dict with `phone` and `email` values extracted from those fields

#### Scenario: sameAs array yields social profile URLs
- **WHEN** the JSON-LD block contains a `"sameAs"` array with values including URLs matching known social domains (instagram.com, facebook.com, twitter.com, linkedin.com, tiktok.com)
- **THEN** the returned dict SHALL include those URLs in a `social_urls` list

#### Scenario: Multiple JSON-LD blocks — most specific type wins
- **WHEN** the HTML contains multiple `<script type="application/ld+json">` elements with different `@type` values
- **THEN** the extractor SHALL prefer the most specific LocalBusiness subtype (`Restaurant`, `MedicalBusiness`, `HealthAndBeautyBusiness`, etc.) over the generic `Organization` or `WebSite` type

#### Scenario: address block extracted and stored
- **WHEN** the JSON-LD block contains a `"address"` object with `"streetAddress"`, `"addressLocality"`, and/or `"addressCountry"`
- **THEN** the returned dict SHALL include an `address` entry assembling those sub-fields into a human-readable string

#### Scenario: Opening hours extracted if present
- **WHEN** the JSON-LD block contains an `"openingHours"` or `"openingHoursSpecification"` field
- **THEN** the returned dict SHALL include the raw `opening_hours` value (string or list, as-is from JSON)

#### Scenario: Malformed JSON-LD block is silently skipped
- **WHEN** a `<script type="application/ld+json">` element contains invalid JSON or a non-dict top-level structure
- **THEN** the extractor SHALL catch the parse error, log a debug-level warning, and continue processing remaining blocks without raising an exception

#### Scenario: No JSON-LD blocks present returns empty dict
- **WHEN** the HTML contains no `<script type="application/ld+json">` elements
- **THEN** `extract_from_html()` SHALL return an empty dict `{}`

### Requirement: JSON-LD extraction results enrich the BusinessLead before contact discovery
The pipeline SHALL call `json_ld_extractor.extract_from_html(html)` on every lead with a `HAS_WEBSITE` status, immediately after `SocialCollector` extraction and before `ContactDiscovery` runs. Extracted values SHALL be merged into the lead using "fill if empty" semantics — existing non-null values on the lead SHALL NOT be overwritten.

#### Scenario: JSON-LD phone fills empty lead.phone
- **WHEN** a lead has `phone=None` after Google Places collection AND the website JSON-LD contains a `telephone` field
- **THEN** the lead's `phone` SHALL be set to the JSON-LD telephone value (after E.164 normalization attempt)

#### Scenario: JSON-LD email fills empty lead.all_emails
- **WHEN** a lead has `all_emails=[]` after Google Places collection AND the website JSON-LD contains an `email` field
- **THEN** that email SHALL be added to `lead.all_emails` with source attribution noting `json_ld`

#### Scenario: JSON-LD sameAs Instagram URL populates lead.instagram_url
- **WHEN** a lead has `instagram_url=None` AND the website JSON-LD `sameAs` array contains an instagram.com URL
- **THEN** `lead.instagram_url` SHALL be set to that URL and `lead.instagram_presence_status` SHALL be set to `FOUND_IN_SCHEMA`

#### Scenario: JSON-LD sameAs Facebook URL populates lead.facebook_url
- **WHEN** a lead has `facebook_url=None` AND the website JSON-LD `sameAs` array contains a facebook.com URL
- **THEN** `lead.facebook_url` SHALL be set to that URL and `lead.facebook_presence_status` SHALL be set to `FOUND_IN_SCHEMA`

#### Scenario: Existing lead phone not overwritten by JSON-LD
- **WHEN** a lead has a non-null `phone` already set from Google Places
- **THEN** `lead.phone` SHALL remain unchanged even if the website JSON-LD contains a different telephone value
