"""
Europe SMB Leads Viewer
=======================
Interactive Streamlit dashboard for browsing, filtering, and exporting
scored leads produced by the pipeline (output/leads.json).

Launch:
    pip install -r viewer/requirements.txt
    streamlit run viewer/app.py
"""

from __future__ import annotations

import io
from pathlib import Path

import pandas as pd
import streamlit as st

# ── Constants ────────────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_FILE = str(ROOT / "output" / "leads.json")

SCORE_COLS = [
    "business_strength_score",
    "website_problem_score",
    "commercial_opportunity_score",
    "instagram_signal_score",
    "contactability_score",
    "lead_priority_score",
]

TABLE_COLS = [
    "company_name",
    "niche",
    "city",
    "country",
    "email",
    "map_url",
    "lead_priority_score",
    "contactability_score",
    "tier",
    "website_status",
    "instagram_status",
]

TIER_COLORS = {1: "🔴", 2: "🟠", 3: "🟡", 4: "⚪"}

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="SMB Leads Viewer",
    page_icon="🏪",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Data loading ─────────────────────────────────────────────────────────────

@st.cache_data(show_spinner="Loading leads…")
def load_leads(path: str) -> pd.DataFrame:
    """Load leads from JSON, normalise into a flat DataFrame."""
    p = Path(path)
    if not p.exists():
        return pd.DataFrame()

    raw = pd.read_json(p)

    # Flatten any nested dicts (shouldn't be many, but future-proof)
    for col in list(raw.columns):
        if raw[col].dtype == object and raw[col].apply(lambda x: isinstance(x, dict)).any():
            try:
                nested = pd.json_normalize(raw[col].dropna())
                nested.index = raw[col].dropna().index
                raw = raw.drop(columns=[col]).join(nested.add_prefix(f"{col}."))
            except Exception:
                pass

    # Ensure list columns are rendered as strings for display
    for col in ["issues_found", "improvement_opportunities"]:
        if col in raw.columns:
            raw[col] = raw[col].apply(
                lambda v: v if isinstance(v, list) else ([] if pd.isna(v) else [str(v)])
            )

    # Coerce guessed_email to string (nullable)
    if "guessed_email" in raw.columns:
        raw["guessed_email"] = raw["guessed_email"].apply(
            lambda v: str(v) if (v is not None and not (isinstance(v, float) and pd.isna(v))) else None
        )

    # Coerce numeric score columns
    for col in SCORE_COLS:
        if col in raw.columns:
            raw[col] = pd.to_numeric(raw[col], errors="coerce")

    # Default sort: best score first
    if "lead_priority_score" in raw.columns:
        raw = raw.sort_values("lead_priority_score", ascending=False).reset_index(drop=True)

    return raw


# ── Sidebar ───────────────────────────────────────────────────────────────────

def render_sidebar(df: pd.DataFrame) -> pd.DataFrame:
    """Render sidebar filters, return filtered DataFrame."""
    st.sidebar.caption(f"{len(df):,} leads total")
    st.sidebar.divider()
    st.sidebar.subheader("Filters")

    filtered = df.copy()

    # Country
    if "country" in df.columns:
        countries = sorted(df["country"].dropna().unique().tolist())
        sel_countries = st.sidebar.multiselect("Country", countries, default=countries)
        if sel_countries:
            filtered = filtered[filtered["country"].isin(sel_countries)]

    # Niche
    if "niche" in df.columns:
        niches = sorted(df["niche"].dropna().unique().tolist())
        sel_niches = st.sidebar.multiselect("Niche", niches, default=niches)
        if sel_niches:
            filtered = filtered[filtered["niche"].isin(sel_niches)]

    # Tier
    if "tier" in df.columns:
        tiers = sorted(df["tier"].dropna().unique().tolist())
        sel_tiers = st.sidebar.multiselect(
            "Tier",
            tiers,
            default=tiers,
            format_func=lambda t: f"{TIER_COLORS.get(t, '')} Tier {t}",
        )
        if sel_tiers:
            filtered = filtered[filtered["tier"].isin(sel_tiers)]

    # Website status
    if "website_status" in df.columns:
        statuses = sorted(df["website_status"].dropna().unique().tolist())
        sel_statuses = st.sidebar.multiselect("Website status", statuses, default=statuses)
        if sel_statuses:
            filtered = filtered[filtered["website_status"].isin(sel_statuses)]

    # Min priority score
    if "lead_priority_score" in df.columns:
        max_score = float(df["lead_priority_score"].max() or 100)
        min_score = st.sidebar.slider(
            "Min priority score",
            min_value=0.0,
            max_value=max_score,
            value=0.0,
            step=0.5,
        )
        filtered = filtered[filtered["lead_priority_score"] >= min_score]

    st.sidebar.divider()
    st.sidebar.metric("Matching leads", f"{len(filtered):,}")

    return filtered


# ── Table ─────────────────────────────────────────────────────────────────────

def render_table(filtered: pd.DataFrame) -> int | None:
    """Render leads table. Returns selected row index or None."""
    st.subheader(f"Leads — {len(filtered):,} matches")

    # Only show columns that exist
    display_cols = [c for c in TABLE_COLS if c in filtered.columns]
    table_df = filtered[display_cols].copy()

    # Format score column
    if "lead_priority_score" in table_df.columns:
        table_df["lead_priority_score"] = table_df["lead_priority_score"].round(1)

    # Tier label with emoji
    if "tier" in table_df.columns:
        table_df["tier"] = table_df["tier"].apply(
            lambda t: f"{TIER_COLORS.get(t, '')} {t}"
        )

    # Column config
    col_config: dict = {
        "company_name":        st.column_config.TextColumn("Company", width="large"),
        "niche":               st.column_config.TextColumn("Niche"),
        "city":                st.column_config.TextColumn("City"),
        "country":             st.column_config.TextColumn("Country"),
        "email":               st.column_config.TextColumn("Email"),
        "map_url":             st.column_config.LinkColumn("Google Maps", display_text="📍 Open"),
        "lead_priority_score": st.column_config.NumberColumn("Score", format="%.1f"),
        "contactability_score":st.column_config.NumberColumn("Contactability", format="%.1f"),
        "tier":                st.column_config.TextColumn("Tier", width="small"),
        "website_status":      st.column_config.TextColumn("Website"),
        "instagram_status":    st.column_config.TextColumn("Instagram"),
    }

    # Row selection (Streamlit ≥1.35 supports on_select; guard with version check)
    import streamlit as _st
    st_ver = tuple(int(x) for x in _st.__version__.split(".")[:2])
    selected_index: int | None = None

    if st_ver >= (1, 35):
        event = st.dataframe(
            table_df,
            width="stretch",
            column_config=col_config,
            on_select="rerun",
            selection_mode="single-row",
            hide_index=True,
        )
        rows = event.selection.get("rows", []) if hasattr(event, "selection") else []
        if rows:
            selected_index = rows[0]
    else:
        st.dataframe(table_df, width="stretch", column_config=col_config, hide_index=True)
        total = len(filtered)
        if total > 0:
            selected_index = st.number_input(
                "Select row to inspect (0-based index)",
                min_value=0,
                max_value=total - 1,
                value=0,
                step=1,
            )

    return selected_index


# ── Detail panel ──────────────────────────────────────────────────────────────

def render_detail(filtered: pd.DataFrame, idx: int | None) -> None:
    """Render expanded detail panel for one selected lead."""
    if idx is None or idx >= len(filtered):
        return

    lead = filtered.iloc[idx]

    with st.expander(f"📋 Lead details — {lead.get('company_name', '(unnamed)')}", expanded=True):
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### 🏢 Business info")
            st.write(f"**Company:** {lead.get('company_name', '—')}")
            st.write(f"**Niche:** {lead.get('niche', '—')}")
            st.write(f"**City:** {lead.get('city', '—')}, {lead.get('country', '—')}")
            st.write(f"**Address:** {lead.get('address') or '—'}")
            st.write(f"**Phone:** {lead.get('phone') or '—'}")

            website = lead.get("website_url") or lead.get("websiteUri")
            if website:
                st.markdown(f"**Website:** [{website}]({website})")
            else:
                st.write("**Website:** —")

            map_url = lead.get("map_url") or lead.get("googleMapsUri")
            if map_url:
                st.markdown(f"**Map:** [Open map]({map_url})")

            email = lead.get("email")
            if email:
                st.markdown(f"**Email:** [{email}](mailto:{email})")

            _SOCIAL_LABELS = {
                "facebook_url":  ("Facebook",  "🔵"),
                "twitter_url":   ("Twitter/X", "🐦"),
                "tiktok_url":    ("TikTok",    "🎵"),
                "linkedin_url":  ("LinkedIn",  "💼"),
                "youtube_url":   ("YouTube",   "▶️"),
                "pinterest_url": ("Pinterest", "📌"),
                "whatsapp_url":  ("WhatsApp",  "💬"),
                "telegram_url":  ("Telegram",  "✈️"),
            }
            social_links = [
                (icon, label, lead[key])
                for key, (label, icon) in _SOCIAL_LABELS.items()
                if lead.get(key)
            ]
            if social_links:
                st.markdown("#### 📱 Social media")
                for icon, label, url in social_links:
                    st.markdown(f"{icon} **{label}:** [{url}]({url})")

        with col2:
            st.markdown("#### 📊 Scores")
            score_data = {
                "Business strength":       lead.get("business_strength_score"),
                "Website problem":         lead.get("website_problem_score"),
                "Commercial opportunity":  lead.get("commercial_opportunity_score"),
                "Instagram signal":        lead.get("instagram_signal_score"),
                "Contactability":          lead.get("contactability_score"),
                "Priority score":          lead.get("lead_priority_score"),
            }
            for label, val in score_data.items():
                if val is not None:
                    bar_val = min(float(val) / 100.0, 1.0)
                    st.progress(bar_val, text=f"{label}: **{float(val):.1f}**")

            t = lead.get("tier")
            if t:
                st.write(f"**Tier:** {TIER_COLORS.get(t, '')} {t}")
            st.write(f"**Website status:** {lead.get('website_status', '—')}")
            st.write(f"**Instagram status:** {lead.get('instagram_status', '—')}")
            lead_source = lead.get("lead_source")
            if lead_source:
                st.write(f"**Lead source:** {lead_source}")
            match_conf = lead.get("match_confidence")
            if match_conf:
                st.write(f"**Match confidence:** {match_conf}")

        st.markdown("---")
        col3, col4 = st.columns(2)

        with col3:
            st.markdown("#### 💬 Outreach")
            angle = lead.get("outreach_angle")
            pitch = lead.get("short_pitch")
            if angle:
                st.markdown(f"**Outreach angle:**\n> {angle}")
            if pitch:
                st.markdown(f"**Short pitch:**\n> {pitch}")

        with col4:
            st.markdown("#### 🔍 Audit findings")
            issues = lead.get("issues_found") or []
            opps   = lead.get("improvement_opportunities") or []

            if isinstance(issues, list) and issues:
                st.markdown("**Issues found:**")
                for i in issues:
                    st.markdown(f"- {i}")
            else:
                st.markdown("**Issues found:** None")

            if isinstance(opps, list) and opps:
                st.markdown("**Improvement opportunities:**")
                for o in opps:
                    st.markdown(f"- {o}")
            else:
                st.markdown("**Improvement opportunities:** None")

        # Contact discovery section
        _all_emails   = lead.get("all_emails")   or []
        _all_phones   = lead.get("all_phones")   or []
        _booking      = lead.get("booking_links") or []
        _whatsapp     = lead.get("whatsapp_links") or []
        _messenger    = lead.get("messenger_links") or []
        _forms        = lead.get("contact_form_urls") or []
        _primary_method = lead.get("primary_contact_method")
        _primary_email  = lead.get("primary_email")
        _guessed_email  = lead.get("guessed_email")

        has_contact_data = any([
            isinstance(_all_emails, list) and _all_emails,
            isinstance(_all_phones, list) and _all_phones,
            isinstance(_booking, list) and _booking,
            isinstance(_whatsapp, list) and _whatsapp,
            isinstance(_messenger, list) and _messenger,
            isinstance(_forms, list) and _forms,
            _primary_method,
            _guessed_email,
        ])

        if has_contact_data:
            st.markdown("---")
            st.markdown("#### 📬 Contacts & Channels")
            if _primary_method:
                st.write(f"**Primary contact method:** {_primary_method}")
            ccol1, ccol2 = st.columns(2)
            with ccol1:
                if isinstance(_all_emails, list) and _all_emails:
                    st.markdown("**Emails:**")
                    for em in _all_emails:
                        st.markdown(f"- [{em}](mailto:{em})")
                if _guessed_email and not _primary_email and not _all_emails:
                    st.markdown(
                        f"⚠️ [{_guessed_email}](mailto:{_guessed_email}) "
                        "(MX verified, not scraped)"
                    )
                if isinstance(_all_phones, list) and _all_phones:
                    st.markdown("**Phones:**")
                    for ph in _all_phones:
                        st.markdown(f"- [{ph}](tel:{ph})")
                if isinstance(_messenger, list) and _messenger:
                    st.markdown("**Messenger:**")
                    for lnk in _messenger:
                        st.markdown(f"- [Open]({lnk})")
            with ccol2:
                if isinstance(_booking, list) and _booking:
                    st.markdown("**Booking links:**")
                    for lnk in _booking:
                        st.markdown(f"- [{lnk}]({lnk})")
                if isinstance(_whatsapp, list) and _whatsapp:
                    st.markdown("**WhatsApp:**")
                    for lnk in _whatsapp:
                        st.markdown(f"- [Open]({lnk})")
                if isinstance(_forms, list) and _forms:
                    st.markdown("**Contact forms:**")
                    for lnk in _forms:
                        st.markdown(f"- [{lnk}]({lnk})")


# ── CSV export ────────────────────────────────────────────────────────────────

def render_export(filtered: pd.DataFrame) -> None:
    """Download button for filtered leads as UTF-8 CSV."""
    # Serialise list columns to strings for CSV
    export_df = filtered.copy()
    for col in ["issues_found", "improvement_opportunities"]:
        if col in export_df.columns:
            export_df[col] = export_df[col].apply(
                lambda v: " | ".join(v) if isinstance(v, list) else str(v or "")
            )

    buf = io.StringIO()
    export_df.to_csv(buf, index=False, encoding="utf-8")
    csv_bytes = buf.getvalue().encode("utf-8")

    st.download_button(
        label=f"⬇ Download CSV ({len(filtered):,} leads)",
        data=csv_bytes,
        file_name="filtered_leads.csv",
        mime="text/csv",
    )


# ── Reachable Leads tab ───────────────────────────────────────────────────────

def _render_reachable_tab(reachable: pd.DataFrame) -> None:
    """Render the Reachable Leads tab with outreach links."""
    if reachable.empty:
        st.info("No reachable leads found with the current filters.")
        return

    # Sort descending by contactability_score
    if "contactability_score" in reachable.columns:
        reachable = reachable.sort_values("contactability_score", ascending=False).reset_index(drop=True)

    st.subheader(f"Reachable Leads — {len(reachable):,} matches")
    st.caption("Leads with contactability_score > 0, sorted by reachability.")

    # Build a display frame with one-click outreach links
    display = pd.DataFrame()
    display["Company"]        = reachable.get("company_name", pd.Series())
    display["Niche"]          = reachable.get("niche",         pd.Series())
    display["City"]           = reachable.get("city",          pd.Series())
    display["Contactability"] = reachable.get("contactability_score", pd.Series())

    # Email column — prefer scraped, fall back to guessed
    def _email_link(row) -> str:
        em = row.get("primary_email") or row.get("email")
        guessed = row.get("guessed_email")
        if em:
            return f"mailto:{em}"
        if guessed:
            return f"mailto:{guessed}"
        return ""

    def _email_label(row) -> str:
        em = row.get("primary_email") or row.get("email")
        guessed = row.get("guessed_email")
        if em:
            return em
        if guessed:
            return f"⚠️ {guessed}"
        return ""

    display["Email"]    = reachable.apply(_email_label, axis=1)
    display["Email URL"] = reachable.apply(_email_link, axis=1)

    # Phone
    display["Phone URL"] = reachable.apply(
        lambda r: f"tel:{r.get('primary_phone') or r.get('phone') or ''}".rstrip(":"),
        axis=1,
    )
    display["Phone"] = reachable.apply(
        lambda r: r.get("primary_phone") or r.get("phone") or "", axis=1
    )

    # WhatsApp — first entry if available
    def _first_link(col_name, row):
        val = row.get(col_name)
        if isinstance(val, list) and val:
            return val[0]
        return ""

    display["WhatsApp"]  = reachable.apply(lambda r: _first_link("whatsapp_links", r), axis=1)
    display["Booking"]   = reachable.apply(lambda r: _first_link("booking_links",  r), axis=1)

    col_config = {
        "Company":        st.column_config.TextColumn("Company",     width="large"),
        "Niche":          st.column_config.TextColumn("Niche"),
        "City":           st.column_config.TextColumn("City"),
        "Contactability": st.column_config.NumberColumn("Score",     format="%.1f"),
        "Email":          st.column_config.TextColumn("Email"),
        "Email URL":      st.column_config.LinkColumn("✉ Email",     display_text="✉ Open"),
        "Phone":          st.column_config.TextColumn("Phone"),
        "Phone URL":      st.column_config.LinkColumn("📞 Call",     display_text="📞 Call"),
        "WhatsApp":       st.column_config.LinkColumn("💬 WhatsApp", display_text="💬 Open"),
        "Booking":        st.column_config.LinkColumn("📅 Booking",  display_text="📅 Open"),
    }

    # Remove empty link columns to avoid broken links
    for link_col in ["Email URL", "Phone URL", "WhatsApp", "Booking"]:
        if link_col in display.columns and not display[link_col].any():
            display = display.drop(columns=[link_col])
            col_config.pop(link_col, None)

    st.dataframe(
        display,
        column_config=col_config,
        hide_index=True,
    )

    render_export(reachable)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    st.title("🏪 Europe SMB Leads Viewer")

    # Data file path — rendered first so it's available before loading
    st.sidebar.title("🏪 SMB Leads")
    new_path = st.sidebar.text_input("Data file", value=DEFAULT_DATA_FILE, key="_data_path_input")
    if new_path != st.session_state.get("_data_path"):
        st.session_state["_data_path"] = new_path
        st.cache_data.clear()

    data_path = st.session_state.get("_data_path", DEFAULT_DATA_FILE)

    # --- Load ---
    p = Path(data_path)
    if not p.exists():
        st.error(f"File not found: `{data_path}`\n\nMake sure the pipeline has run and produced output.")
        st.stop()

    df = load_leads(data_path)
    if df.empty:
        st.warning("No leads found in the file.")
        st.stop()

    # --- Filter ---
    filtered = render_sidebar(df)

    # --- Tabs ---
    if "contactability_score" in filtered.columns:
        reachable = filtered[filtered["contactability_score"] > 0].copy()
    else:
        reachable = pd.DataFrame()
    reachable_count = len(reachable)

    tab_all, tab_reachable = st.tabs([
        "All Leads",
        f"Reachable Leads ({reachable_count})",
    ])

    with tab_all:
        # --- Table ---
        selected_idx = render_table(filtered)

        # --- Export ---
        render_export(filtered)

        # --- Detail ---
        render_detail(filtered, selected_idx)

    with tab_reachable:
        _render_reachable_tab(reachable)


if __name__ == "__main__":
    main()
