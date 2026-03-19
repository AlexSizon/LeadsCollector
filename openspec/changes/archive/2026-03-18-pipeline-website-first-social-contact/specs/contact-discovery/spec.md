## ADDED Requirements

### Requirement: JSON-LD extraction results feed into the contact pool before HTML scraping
The system SHALL, when processing a lead with `website_status == HAS_WEBSITE`, call `json_ld_extractor.extract_from_html(html)` before `ContactDiscovery.extract()` runs and use the results to pre-populate the contact pool. Phone and email values extracted from JSON-LD SHALL be merged into the lead using fill-if-empty semantics, so that `ContactDiscovery` scraping adds to — rather than replaces — the structured data findings.

#### Scenario: JSON-LD email pre-populates all_emails before scraping
- **WHEN** JSON-LD extraction returns an `email` value AND `lead.all_emails` is empty at that point
- **THEN** that email SHALL be added to `lead.all_emails` before `ContactDiscovery.extract()` is called, so the scraping pass deduplicates against it rather than adding it again

#### Scenario: JSON-LD phone pre-populates all_phones before scraping
- **WHEN** JSON-LD extraction returns a `phone` value AND `lead.all_phones` is empty
- **THEN** that phone SHALL be added to `lead.all_phones` (E.164 normalised) before `ContactDiscovery.extract()` is called

#### Scenario: ContactDiscovery deduplicates against JSON-LD pre-populated values
- **WHEN** `ContactDiscovery.extract()` finds the same email already present in `all_emails` from JSON-LD
- **THEN** the email SHALL appear only once in the final `all_emails` list

#### Scenario: JSON-LD-sourced contacts do not suppress ContactDiscovery scraping
- **WHEN** JSON-LD yielded a phone but no email
- **THEN** `ContactDiscovery.extract()` SHALL still run the full HTML scraping pass to find email addresses

### Requirement: Contact extraction runs on social-stub leads with bio-discovered website URLs
The system SHALL attempt `ContactDiscovery.extract()` on social-stub leads (leads created from `SocialCandidate` objects with no Google Places origin) when those leads have a non-null `website_url` discovered from social bio data. The extraction SHALL use the bio-discovered URL as the target, applying the same logic as for Google Places leads.

#### Scenario: Social-stub lead with bio website gets contact discovery
- **WHEN** a stub `BusinessLead` is created from a `SocialCandidate` with `website_url` non-null AND `enable_contact_discovery` is `true`
- **THEN** the pipeline SHALL call `ContactDiscovery.extract()` for that lead using the bio-discovered website URL

#### Scenario: Social-stub lead without website URL skips contact discovery
- **WHEN** a stub `BusinessLead` created from a `SocialCandidate` has `website_url=None`
- **THEN** `ContactDiscovery.extract()` SHALL NOT be called for that lead and contact fields SHALL remain as populated from the bio extraction in `SocialCandidate`

#### Scenario: Contact data from bio is not overwritten by empty scraping result
- **WHEN** a social-stub lead has `all_emails` pre-populated from the `SocialCandidate.email` field AND `ContactDiscovery.extract()` finds no email on the bio-discovered website
- **THEN** `lead.all_emails` SHALL retain the pre-existing bio-sourced email

### Requirement: EmailGuesser wired as post-extraction fallback when no email found
The system SHALL, when `enable_email_guesser` is `true` (default: `true`), call `EmailGuesser.guess(lead.website_url, lead.niche)` for any lead that has `website_url` non-null AND `all_emails` is empty after `ContactDiscovery` completes. The result, if non-null, SHALL be written to `lead.guessed_email`. This requirement formalises the wiring of the already-implemented `EmailGuesser` module which currently exists but is never called.

#### Scenario: Guesser called when contact extraction finds no email and website is known
- **WHEN** `ContactDiscovery.extract()` completes with `all_emails=[]` AND `lead.website_url` is non-null AND `enable_email_guesser` is `true`
- **THEN** the pipeline SHALL call `EmailGuesser.guess(lead.website_url, lead.niche)` and store any non-null result in `lead.guessed_email`

#### Scenario: Guesser skipped when email already found by scraping or JSON-LD
- **WHEN** `all_emails` is non-empty after contact extraction (from scraping or JSON-LD)
- **THEN** `EmailGuesser` SHALL NOT be called for that lead

#### Scenario: Guesser skipped when website is unavailable
- **WHEN** `lead.website_url` is `None` or `lead.website_status` is not `HAS_WEBSITE`
- **THEN** `EmailGuesser` SHALL NOT be called for that lead

#### Scenario: Guesser failure does not block pipeline
- **WHEN** `EmailGuesser.guess()` raises an exception (DNS timeout, dnspython not installed, etc.)
- **THEN** the exception SHALL be caught, a debug warning SHALL be logged, `lead.guessed_email` SHALL remain `None`, and the pipeline SHALL continue

#### Scenario: Guesser disabled via config flag
- **WHEN** `enable_email_guesser` is explicitly `false` in the run config
- **THEN** `EmailGuesser` SHALL NOT be called for any lead
