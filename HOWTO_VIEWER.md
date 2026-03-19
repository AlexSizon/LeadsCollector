# How to launch the SMB Leads Viewer

The viewer is an interactive Streamlit dashboard for browsing, filtering,
and exporting the scored leads produced by the pipeline.

---

## Prerequisites

- Python 3.9 or newer (same Python used by the pipeline)
- Pipeline run completed — `output/leads.json` must exist

---

## Setup (one-time)

```bash
pip install -r viewer/requirements.txt
```

This installs `streamlit` and `pandas` into your current Python environment.
It does **not** affect the pipeline's own dependencies.

---

## Launch

```bash
streamlit run viewer/app.py
```

Streamlit will print a local URL (usually `http://localhost:8501`) and open
it in your default browser automatically.

---

## Using the viewer

| Area | What it does |
|---|---|
| **Sidebar — Data file** | Path to the leads JSON. Default: `output/leads.json`. Change it and press Enter to reload. |
| **Sidebar — Filters** | Multi-select by Country, Niche, Tier, Website Status; drag the Score slider to set a minimum priority score. |
| **Matching leads counter** | Shows how many leads pass the current filters. |
| **Leads table** | Sorted by priority score (highest first). Click any column header to re-sort. |
| **Select a row** | Click a row (Streamlit ≥ 1.35) or type a row number (older versions) to open the detail panel. |
| **Detail panel** | Full lead record: address, phone, website & map links, sub-scores with progress bars, outreach angle, pitch, and audit findings. |
| **Download CSV** | Exports **all currently filtered** leads (not just the visible page) as UTF-8 CSV. |

---

## Pointing at a different output file

1. Type the path in the **Data file** box in the sidebar (e.g. `output/leads_portugal_supplement.json`)
2. Press **Enter** — the viewer reloads from that file automatically.

Or launch with the file specified directly via Streamlit's `--` argument separator:

```bash
streamlit run viewer/app.py -- --data output/leads_portugal_supplement.json
```

*(This requires a small argument parser in `app.py`; the sidebar input achieves
the same without any extra flags.)*

---

## Stopping the server

Press **Ctrl+C** in the terminal where Streamlit is running.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `File not found: output/leads.json` | Run the pipeline first: `python run_europe_smb.py` |
| `ModuleNotFoundError: streamlit` | Run `pip install -r viewer/requirements.txt` |
| Browser doesn't open | Navigate manually to `http://localhost:8501` |
| Filters show no results | Reset all multi-selects and drag the score slider back to 0 |
