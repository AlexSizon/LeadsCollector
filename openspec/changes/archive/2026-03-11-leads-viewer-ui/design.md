## Context

The pipeline writes scored leads to `output/leads.json` (3 000+ records, ~3 MB). 
The only current way to view results is opening the CSV in a spreadsheet, which requires manual setup and offers no scoring-aware presentation. The viewer is a read-only companion tool that runs locally and loads the existing output file.

## Goals / Non-Goals

**Goals:**
- One-command launch (`streamlit run viewer/app.py`)
- Filter leads by country, niche, tier, website status, and minimum priority score
- Sort the leads table by any column
- Expand a selected lead to view full detail (outreach angle, pitch, audit issues, phone, website)
- Export the current filtered view as CSV
- Clearly document the launch procedure in `HOWTO_VIEWER.md`

**Non-Goals:**
- Editing or updating lead records
- Writing back to `leads.json`
- Authentication or multi-user access
- Deployment to cloud / hosting
- Real-time pipeline re-runs from the UI

## Decisions

**Framework: Streamlit over Flask/Dash/raw HTML**
Streamlit requires no HTML/JS, runs with `pip install streamlit`, and provides built-in widgets (multiselect, slider, dataframe) that match every required filter exactly. Flask or Dash would require frontend code and significantly more boilerplate for the same outcome.

**Data loading: pandas read from `output/leads.json`**
JSON is richer than CSV (nested fields, null preservation) and is the canonical output. A single `pd.read_json()` + `pd.json_normalize()` call flattens all fields. The file path defaults to `output/leads.json` but is overridable via a sidebar file-path input so the viewer works with any run's output.

**Detail panel: `st.expander` on selected row index**
Rather than a separate page, an expander below the table is stateless and keeps context visible. Row selection via `st.dataframe(on_select="rerun")` (Streamlit ≥1.35) or via a numeric index input for older versions.

**No server-side state / database**
All filtering happens in-memory with pandas. For 3 000–10 000 leads this is sub-second. No SQLite or caching layer is needed.

**Separate `viewer/requirements.txt`**
Keeps viewer dependencies isolated from the pipeline's runtime. Pipeline already uses `requests`, `bs4`, `pydantic` etc. — Streamlit should not bleed into those.

## Risks / Trade-offs

- **Streamlit version drift** → Pin `streamlit>=1.32,<2` and `pandas>=2.0,<3` in `viewer/requirements.txt`.
- **Large JSON parse time** → `pd.read_json` on 3 MB is ~100 ms; acceptable. Cache with `@st.cache_data`.
- **Row-selection API changed in Streamlit 1.35** → Use `st.dataframe(on_select="rerun", selection_mode="single-row")` with a version guard; fall back to numeric index input.
- **leads.json path hardcoded** → Sidebar text input lets user point to any output file without modifying code.
