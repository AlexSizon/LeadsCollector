## ADDED Requirements

### Requirement: Normalise company name, phone, domain, and category
The system SHALL normalise raw business fields into canonical forms before any downstream processing.

#### Scenario: Phone normalised to E.164 international format
- **WHEN** a raw phone number is `030 12345678`
- **THEN** the normaliser SHALL produce `+493012345678`

#### Scenario: Domain extracted from website URL to root domain
- **WHEN** `website_url` is `https://www.smilestudio-berlin.de/contact`
- **THEN** the normaliser SHALL set `root_domain` to `smilestudio-berlin.de`

#### Scenario: Company name normalised to lowercase stripped form
- **WHEN** `company_name` is `  Smile Studio Berlin GmbH  `
- **THEN** the normalised form SHALL be `smile studio berlin gmbh`

#### Scenario: Category mapped to controlled vocabulary
- **WHEN** the Google Places `types` array contains `["dentist", "health", "point_of_interest"]`
- **THEN** the normaliser SHALL map the primary category to `dentist` from the controlled vocabulary

### Requirement: Detect social links and classify website presence type
The system SHALL inspect the `website_url` field and any detectable social profiles to determine whether the business has a real owned web presence.

#### Scenario: No website URL present
- **WHEN** `website_url` is null and no social profiles are detected
- **THEN** `website_status` SHALL be set to `NO_WEBSITE`

#### Scenario: Website URL is a known social/directory domain
- **WHEN** `website_url` resolves to a domain in the social/directory domain list (e.g., `instagram.com`, `facebook.com`, `linktree.ee`)
- **THEN** `website_status` SHALL be set to `SOCIAL_ONLY`

#### Scenario: Business is classified as SMB
- **WHEN** the business has fewer than 5 Google Places locations detected and is in a targeted niche
- **THEN** `is_smb` SHALL be set to `true`
