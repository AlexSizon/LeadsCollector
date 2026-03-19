## ADDED Requirements

### Requirement: Dashboard loads leads from JSON file
The viewer SHALL load leads from a JSON file path specified in the sidebar (defaulting to `output/leads.json`).
All lead fields from the pipeline output schema SHALL be available for display and filtering.
The file SHALL be cached with `@st.cache_data` so reloads are not triggered on every widget interaction.

#### Scenario: Default file loads on startup
- **WHEN** the user opens the dashboard with no arguments
- **THEN** `output/leads.json` is loaded automatically and the lead count is shown in the sidebar

#### Scenario: Custom file path
- **WHEN** the user enters a different path in the sidebar "Data file" input and presses Enter
- **THEN** the dashboard reloads leads from the specified file

#### Scenario: File not found
- **WHEN** the specified file does not exist
- **THEN** an error message SHALL be displayed and no table is rendered

### Requirement: Sidebar filters narrow the displayed leads
The viewer SHALL provide sidebar controls to filter leads by:
- **Country**: multi-select (all countries in dataset as options)
- **Niche**: multi-select (all niches in dataset as options)
- **Tier**: multi-select of values 1, 2, 3, 4
- **Website status**: multi-select (all statuses in dataset)
- **Minimum priority score**: numeric slider from 0 to 100

All filters SHALL be combinable (AND logic).
The sidebar SHALL display the count of matching leads after applying all active filters.

#### Scenario: Filter by tier
- **WHEN** the user selects Tier 1 and Tier 2 in the Tier filter
- **THEN** only leads with `tier` equal to 1 or 2 are shown in the table

#### Scenario: Filter by minimum score
- **WHEN** the user sets minimum priority score to 55
- **THEN** only leads with `lead_priority_score >= 55` are shown

#### Scenario: No filter selections
- **WHEN** all filter controls are at their default (all selected / slider at 0)
- **THEN** all leads are displayed

### Requirement: Main table displays key fields
The viewer SHALL render a sortable, scrollable table showing at minimum:
`company_name`, `niche`, `city`, `country`, `lead_priority_score`, `tier`, `website_status`, `instagram_status`.

The table SHALL be sortable by clicking column headers.
Score column SHALL be formatted to one decimal place.
Tier column SHALL be visually highlighted: Tier 1 = highest prominence.

#### Scenario: Default sort order
- **WHEN** the table first renders
- **THEN** leads are sorted by `lead_priority_score` descending

#### Scenario: Column sort
- **WHEN** the user clicks a column header
- **THEN** the table re-sorts by that column

### Requirement: Lead detail panel shows full record
The viewer SHALL provide a detail view for one selected lead showing all available fields:
address, phone, website URL (as clickable link), map URL (as link), outreach angle, short pitch,
issues found, improvement opportunities, all sub-scores, and OSM/source metadata.

#### Scenario: Select a lead
- **WHEN** the user selects a row in the table
- **THEN** an expander below the table opens showing the full detail of that lead

#### Scenario: No lead selected
- **WHEN** no row is selected
- **THEN** the detail panel is hidden or shows a prompt to select a row

### Requirement: Export filtered results as CSV
The viewer SHALL provide a "Download CSV" button that exports all currently filtered leads
(not just the visible page) as a UTF-8 CSV file.

#### Scenario: Download filtered leads
- **WHEN** the user has applied filters and clicks "Download CSV"
- **THEN** a CSV file is downloaded containing only the filtered leads with all fields

### Requirement: Launch instructions documented in HOWTO_VIEWER.md
A file `HOWTO_VIEWER.md` SHALL exist at the project root containing:
- Prerequisites (Python 3.9+)
- Installation command (`pip install -r viewer/requirements.txt`)
- Launch command (`streamlit run viewer/app.py`)
- How to point at a different output file
- Screenshot description or sample output description

#### Scenario: First-time setup
- **WHEN** a user follows HOWTO_VIEWER.md from a clean clone
- **THEN** they can launch the dashboard in three commands or fewer
