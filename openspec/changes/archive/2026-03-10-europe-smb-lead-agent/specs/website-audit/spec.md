## ADDED Requirements

### Requirement: Determine website_status using HTTP and DNS checks
The system SHALL attempt to resolve and fetch each business's domain and SHALL assign exactly one `website_status` enum value based on the outcome.

#### Scenario: Domain does not resolve
- **WHEN** DNS resolution fails for the root domain
- **THEN** `website_status` SHALL be `BROKEN_WEBSITE`

#### Scenario: HTTP fetch returns 5xx or connection error
- **WHEN** the HTTP request to the website returns a 5xx status code or raises a connection error
- **THEN** `website_status` SHALL be `BROKEN_WEBSITE`

#### Scenario: Domain resolves to a parked page
- **WHEN** the fetched page contains known parking-page fingerprints (e.g., "This domain is for sale", "Sedo", "GoDaddy Parking")
- **THEN** `website_status` SHALL be `BROKEN_WEBSITE`

#### Scenario: Domain resolves and returns valid business page
- **WHEN** DNS resolves, HTTP returns 200, and no parking-page fingerprint is found
- **THEN** `website_status` SHALL be `HAS_WEBSITE`

#### Scenario: Audit not run when website_status is not HAS_WEBSITE
- **WHEN** `website_status` is `NO_WEBSITE`, `SOCIAL_ONLY`, or `BROKEN_WEBSITE`
- **THEN** all audit score fields SHALL be set to `null` and the audit SHALL NOT be run

### Requirement: Run technical audit for reachable websites
The system SHALL check a set of technical signals when a website is reachable.

#### Scenario: HTTPS enforcement check
- **WHEN** the website is reachable over HTTP but does not redirect to HTTPS
- **THEN** the audit SHALL record `"No HTTPS redirect"` as an issue

#### Scenario: Mobile viewport tag check
- **WHEN** the page HTML does not contain `<meta name="viewport"`
- **THEN** the audit SHALL record `"Missing mobile viewport meta tag"` as an issue

#### Scenario: SSL validity check
- **WHEN** the SSL certificate is expired or invalid
- **THEN** the audit SHALL record `"Invalid or expired SSL certificate"` as an issue

### Requirement: Run SEO audit for reachable websites
The system SHALL check basic on-page SEO signals for reachable websites.

#### Scenario: Missing title tag
- **WHEN** the page HTML has no `<title>` tag or an empty title
- **THEN** the audit SHALL record `"Missing page title"` as an issue

#### Scenario: Missing meta description
- **WHEN** the page HTML has no `<meta name="description"` tag
- **THEN** the audit SHALL record `"Missing meta description"` as an issue

#### Scenario: Missing or multiple H1 tags
- **WHEN** the page HTML contains zero or more than one `<h1>` tag
- **THEN** the audit SHALL record the corresponding issue

### Requirement: Run UX/CRO audit for reachable websites
The system SHALL check conversion-relevant signals for reachable websites.

#### Scenario: No detectable CTA
- **WHEN** the page HTML contains no button elements and no links matching CTA keyword patterns (book, reserve, appointment, contact, anfragen, buchen, reservar, afspraak)
- **THEN** the audit SHALL record `"No clear CTA found"` as an issue

#### Scenario: No click-to-call link
- **WHEN** the page HTML contains no `href="tel:` link
- **THEN** the audit SHALL record `"No click-to-call link found"` as an issue

#### Scenario: No booking or contact form detected
- **WHEN** the page HTML contains no `<form` element
- **THEN** the audit SHALL record `"No contact or booking form found"` as an issue
