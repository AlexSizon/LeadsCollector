## ADDED Requirements

### Requirement: Normalize extracted phone numbers to E.164 format
`ContactDiscovery` SHALL normalize every extracted phone number to E.164 international format using `normalizer.normalize_phone()` before adding it to `all_phones`. If normalization fails (unparseable number or missing region code), the raw string SHALL be kept as a fallback.

#### Scenario: Phone from tel link normalized to E.164
- **WHEN** the website HTML contains `<a href="tel:+34 91 123 45 67">`
- **THEN** `ContactDiscovery` SHALL store `"+34911234567"` (E.164) in `all_phones`, not the raw string `"+34 91 123 45 67"`

#### Scenario: Phone in local format normalized with country hint from niche-city context
- **WHEN** the website HTML contains `<a href="tel:91 123 45 67">` and the business country is Spain
- **THEN** `ContactDiscovery` SHALL attempt to normalize using `"ES"` as the default region and store the E.164 result if successful

#### Scenario: Unparseable phone retained as raw string
- **WHEN** `normalizer.normalize_phone()` raises an exception or returns `None` for a given input
- **THEN** the raw input string SHALL be stored in `all_phones` as a fallback, and a debug-level log message SHALL be emitted

#### Scenario: Duplicate phone in different formats deduplicated after normalization
- **WHEN** the same phone number appears twice in HTML (e.g., as `tel:+34911234567` and as visible text `91 123 45 67`)
- **THEN** `all_phones` SHALL contain only one entry after normalization and deduplication

## MODIFIED Requirements

### Requirement: Extract all public contact channels from a business entity
The system SHALL, when `enable_contact_discovery` is `true`, extract all publicly available contact information for a business from its website HTML, social profile data, and OSM tags, and store the result in a structured `ContactResult` object. All extracted phone numbers SHALL be normalized to E.164 format using `normalizer.normalize_phone()` before storage; normalization failures SHALL fall back to preserving the raw string.

#### Scenario: Email extracted from mailto link
- **WHEN** the website HTML contains an `<a href="mailto:info@example.com">` element
- **THEN** `ContactDiscovery.extract()` SHALL include `"info@example.com"` in `all_emails`

#### Scenario: Email extracted from visible text via regex
- **WHEN** the website HTML contains a visible email address string not wrapped in a mailto link
- **THEN** that email SHALL be extracted provided it passes false-positive filtering (no example.*, test.*, *.png, *.jpg patterns)

#### Scenario: Phone extracted from tel link and normalized
- **WHEN** the website HTML contains `<a href="tel:+34911234567">`
- **THEN** that phone SHALL be normalized to E.164 (`"+34911234567"`) and included in `all_phones`

#### Scenario: WhatsApp link detected
- **WHEN** the website HTML contains a `wa.me/` or `api.whatsapp.com/send` link
- **THEN** the canonical WhatsApp URL SHALL be added to `whatsapp_links`
