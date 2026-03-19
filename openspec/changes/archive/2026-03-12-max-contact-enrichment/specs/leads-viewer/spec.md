## ADDED Requirements

### Requirement: Reachable Leads tab shows only contactable leads
The viewer SHALL provide a dedicated "Reachable Leads" tab that filters to leads with `contactability_score > 0`, sorted descending by score.

#### Scenario: Tab shows only contactable leads
- **WHEN** the user selects the "Reachable Leads" tab
- **THEN** only leads with `contactability_score > 0` SHALL be displayed, sorted by `contactability_score` descending

#### Scenario: Tab count shown in tab label
- **WHEN** the dataset is loaded
- **THEN** the tab label SHALL display the count in parentheses, e.g. "Reachable Leads (412)"

#### Scenario: Empty state when no contactable leads
- **WHEN** all leads have `contactability_score = 0`
- **THEN** the tab SHALL display an informational message: "No leads with contact data found. Enable contact discovery and re-run the pipeline."

### Requirement: One-click outreach links in the Reachable Leads tab
Each row in the Reachable Leads tab SHALL display native clickable outreach links for all available channels.

#### Scenario: Email shown as mailto link
- **WHEN** `primary_email` or `guessed_email` is non-null
- **THEN** the email cell SHALL render as a `mailto:` hyperlink

#### Scenario: Phone shown as tel link
- **WHEN** `primary_phone` is non-null
- **THEN** the phone cell SHALL render as a `tel:` hyperlink

#### Scenario: WhatsApp shown as clickable link
- **WHEN** `whatsapp_links` is non-empty
- **THEN** the first WhatsApp link SHALL be rendered as a clickable URL

#### Scenario: Booking link shown as clickable link
- **WHEN** `booking_links` is non-empty
- **THEN** the first booking link SHALL be rendered as a clickable URL

### Requirement: Guessed email flagged visually in viewer
The viewer SHALL visually distinguish guessed emails from directly scraped emails.

#### Scenario: Guessed email shown with warning indicator
- **WHEN** `guessed_email` is non-null and `primary_email` is null
- **THEN** the email field in the detail panel SHALL display the guessed email with a ⚠️ prefix and label "(MX verified, not scraped)"
