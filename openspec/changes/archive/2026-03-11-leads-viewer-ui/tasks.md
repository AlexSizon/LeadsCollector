## 1. Project Scaffold

- [x] 1.1 Create `viewer/` directory and `viewer/__init__.py`
- [x] 1.2 Create `viewer/requirements.txt` with pinned `streamlit>=1.32,<2` and `pandas>=2.0,<3`

## 2. Data Loading

- [x] 2.1 Implement `load_leads(path)` function in `viewer/app.py` using `pd.read_json` + `@st.cache_data`
- [x] 2.2 Handle file-not-found with a user-facing `st.error` message and early return
- [x] 2.3 Add sidebar "Data file" text input defaulting to `output/leads.json`

## 3. Sidebar Filters

- [x] 3.1 Add Country multi-select (populated from dataset values, all selected by default)
- [x] 3.2 Add Niche multi-select (populated from dataset values, all selected by default)
- [x] 3.3 Add Tier multi-select with options [1, 2, 3, 4], all selected by default
- [x] 3.4 Add Website Status multi-select (populated from dataset values, all selected by default)
- [x] 3.5 Add Minimum Priority Score slider (0–100, step 0.5, default 0)
- [x] 3.6 Apply all filters with AND logic and display matching lead count in sidebar

## 4. Main Leads Table

- [x] 4.1 Render filtered leads using `st.dataframe` with column config (score → 1dp, tier highlighted)
- [x] 4.2 Default sort by `lead_priority_score` descending before rendering
- [x] 4.3 Enable row selection (`on_select="rerun"`, `selection_mode="single-row"`) with version guard fallback to index input

## 5. Lead Detail Panel

- [x] 5.1 Render `st.expander("Lead details")` below the table, hidden when no row selected
- [x] 5.2 Display full lead fields: address, phone, website (clickable), map URL (clickable)
- [x] 5.3 Display score breakdown: business_strength, website_problem, commercial_opportunity, instagram_signal, lead_priority_score
- [x] 5.4 Display outreach_angle, short_pitch in dedicated text blocks
- [x] 5.5 Display issues_found and improvement_opportunities as bulleted lists (or "None" if empty)

## 6. CSV Export

- [x] 6.1 Add `st.download_button("Download CSV", ...)` below the table exporting the full filtered DataFrame as UTF-8 CSV

## 7. Documentation

- [x] 7.1 Create `HOWTO_VIEWER.md` at project root covering prerequisites, install, launch, and custom file path usage
