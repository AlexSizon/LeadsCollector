## ADDED Requirements

### Requirement: Extract all public contact channels from a business entity
The system SHALL, when `enable_contact_discovery` is `true`, extract all publicly available contact information for a business from its website HTML, social profile data, and OSM tags, and store the result in a structured `ContactResult` object.

#### Scenario: Email extracted from mailto link
- **WHEN** the website HTML contains an `<a href="mailto:info@example.com">` element
- **THEN** `ContactDiscovery.extract()` SHALL include `"info@example.com"` in `all_emails`

#### Scenario: Email extracted from visible text via regex
- **WHEN** the website HTML contains a visible email address string not wrapped in a mailto link
- **THEN** that email SHALL be extracted provided it passes false-positive filtering (no example.*, test.*, *.png, *.jpg patterns)

#### Scenario: Phone extracted from tel link
- **WHEN** the website HTML contains `<a href="tel:+34911234567">`
- **THEN** that phone SHALL be included in `all_phones`

#### Scenario: WhatsApp link detected
- **WHEN** the website HTML contains a `wa.me/` or `api.whatsapp.com/send` link
- **THEN** the canonical WhatsApp URL SHALL be added to `whatsapp_links`

#### Scenario: Booking link detected
- **WHEN** the website HTML contains a link to a known booking platform (OpenTable, TheFork, Booksy, Calendly, etc.) or contains path segments `/booking`, `/reservations`, `/appointments`
- **THEN** that URL SHALL be added to `booking_links`

#### Scenario: Contact form URL detected
- **WHEN** the website contains an internal page link with path matching `/contact`, `/kontakt`, `/contacto`, `/contacte`, `/contact-us`
- **THEN** that URL SHALL be added to `contact_form_urls`

#### Scenario: Contact page fetched for additional email extraction
- **WHEN** the main page yields no email AND a contact-page URL was detected
- **THEN** `ContactDiscovery` SHALL make one additional HTTP GET to the contact page (timeout ≤ 5s) and attempt email extraction from its HTML

#### Scenario: No additional requests when main page has email
- **WHEN** `all_emails` is non-empty after processing the main page
- **THEN** NO additional HTTP requests SHALL be made for contact sub-pages

### Requirement: Normalise and deduplicate extracted contacts
The system SHALL normalise all extracted contact values and remove duplicates before returning the `ContactResult`.

#### Scenario: Emails normalised to lowercase
- **WHEN** the HTML contains `Info@Example.COM`
- **THEN** the stored email SHALL be `info@example.com`

#### Scenario: Duplicate emails deduplicated
- **WHEN** the same email address appears in both the main page and a contact sub-page
- **THEN** it SHALL appear only once in `all_emails`

#### Scenario: Phones normalised where possible
- **WHEN** a phone number can be parsed as E.164 (e.g. `+34 91 123 45 67`)
- **THEN** the normalised form `+34911234567` SHALL be stored alongside the raw value

### Requirement: Select primary contact per type
The system SHALL determine a `primary_email`, `primary_phone`, and `primary_contact_method` from the extracted contacts using a priority ordering.

#### Scenario: Primary email preference order
- **WHEN** multiple emails are found
- **THEN** the system SHALL prefer, in order: official website email → contact page email → Google Places email → social platform email

#### Scenario: Primary phone preference order
- **WHEN** multiple phones are found
- **THEN** the system SHALL prefer: Google Places phone → website tel link → social platform phone

#### Scenario: Primary contact method determined
- **WHEN** a primary email is available
- **THEN** `primary_contact_method` SHALL be `"email"`

#### Scenario: Primary contact method falls back to next available channel
- **WHEN** no email is found but a phone is available
- **THEN** `primary_contact_method` SHALL be `"phone"`

#### Scenario: Booking link elevated for booking-heavy niches
- **WHEN** the business niche is in the booking-heavy list (restaurant, beauty salon, barbershop, spa, dentist) AND no email is found AND a booking link exists
- **THEN** `primary_contact_method` SHALL be `"booking_link"` ahead of contact form

### Requirement: Populate BusinessLead contact fields from ContactResult
The system SHALL write the extracted `ContactResult` back onto the `BusinessLead` object after contact discovery runs.

#### Scenario: All contact fields populated
- **WHEN** `ContactDiscovery.extract()` completes
- **THEN** the following fields on `BusinessLead` SHALL be updated: `primary_email`, `all_emails`, `primary_phone`, `all_phones`, `whatsapp_links`, `messenger_links`, `booking_links`, `contact_form_urls`, `primary_contact_method`

#### Scenario: Existing non-null fields not overwritten
- **WHEN** `BusinessLead.phone` was already set by the OSM/Places stage
- **THEN** `primary_phone` SHALL prefer that existing value per the priority ordering

### Requirement: Contact discovery does not invent contacts
The system SHALL never generate, guess, or construct contact values that are not explicitly found in the source data.

#### Scenario: No email guessing from domain
- **WHEN** a business has a known website domain but no explicit email is found on any page
- **THEN** `all_emails` SHALL remain empty; no `info@<domain>` or similar SHALL be constructed

### Requirement: Feature flag controls contact discovery activation
The system SHALL only run contact discovery when `enable_contact_discovery: true` is in the run configuration.

#### Scenario: Contact discovery disabled by default
- **WHEN** `enable_contact_discovery` is absent or `false`
- **THEN** NO additional HTTP requests for contact pages SHALL be made and `ContactResult` fields SHALL retain any values already set by `SocialCollector`
