## Why

The pipeline produces `output/leads.json` and `output/leads.csv` with 3 000+ scored leads, but there is no way to browse, filter, or inspect them without a spreadsheet tool. A local visual interface gives the user instant exploratory access — filter by tier, country, niche, or website status; inspect individual leads; and export a targeted sub-list.

## What Changes

- New interactive web dashboard (`viewer/app.py`) built with Streamlit — zero extra infrastructure, launched with one command.
- Sidebar filters: country, niche, tier (1–4), website status, minimum priority score.
- Main table: sortable leads table with all key fields highlighted (score, tier, website status, niche).
- Detail panel: click a lead row to expand full details (address, phone, website, outreach angle, short pitch, audit issues).
- Export: download the current filtered view as CSV.
- `viewer/requirements.txt` listing Streamlit + pandas dependencies.
- `HOWTO_VIEWER.md` at project root explaining setup and launch in three commands.

## Capabilities

### New Capabilities
- `leads-viewer`: Interactive Streamlit dashboard for browsing, filtering, and exporting scored leads.

### Modified Capabilities
<!-- No existing spec-level behavior changes. -->

## Impact

- New directory `viewer/` with `app.py` and `requirements.txt`.
- New file `HOWTO_VIEWER.md` at project root.
- No changes to existing pipeline code or output format.
- Runtime dependency: `streamlit>=1.32`, `pandas>=2.0` (viewer only, not pipeline).
