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
import json
from pathlib import Path

import pandas as pd
import streamlit as st

from src.enums import CampaignExecutionMode, WebsiteStatus
from src.models import BusinessLead
from src.outreach import (
    OutreachStore,
    SenderProfile,
    approve_campaign_item,
    create_campaign_draft,
    execute_campaign,
    manually_suppress_contact,
    preflight_sender_profile,
    record_campaign_feedback,
    stable_lead_id,
)

# ── Constants ────────────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_FILE = str(ROOT / "output" / "leads.json")
DEFAULT_OUTREACH_DB = str(ROOT / "data" / "outreach.db")
DEFAULT_OUTREACH_EXPORT_DIR = str(ROOT / "output" / "outreach_campaigns")

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


@st.cache_resource(show_spinner=False)
def load_outreach_store(path: str) -> OutreachStore:
    """Open the local outreach SQLite store."""
    return OutreachStore(path)


def _row_to_list(value) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    return [str(value)]


def _row_to_optional_str(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def _row_contact_provenance(row: pd.Series) -> dict[str, str]:
    provenance: dict[str, str] = {}
    for key, value in row.items():
        if key.startswith("contact_provenance.") and value is not None and not pd.isna(value):
            provenance[key.split(".", 1)[1]] = str(value)
    return provenance


def _row_to_business_lead(row: pd.Series) -> BusinessLead:
    status_raw = _row_to_optional_str(row.get("website_status")) or WebsiteStatus.UNKNOWN.value
    lead = BusinessLead(
        company_name=_row_to_optional_str(row.get("company_name")) or "",
        niche=_row_to_optional_str(row.get("niche")) or "",
        city=_row_to_optional_str(row.get("city")) or "",
        country=_row_to_optional_str(row.get("country")) or "",
        place_id=_row_to_optional_str(row.get("place_id")),
        address=_row_to_optional_str(row.get("address")),
        phone=_row_to_optional_str(row.get("phone")),
        email=_row_to_optional_str(row.get("email")),
        google_rating=row.get("google_rating"),
        google_reviews_count=row.get("google_reviews_count"),
        website_url=_row_to_optional_str(row.get("website_url")),
        website_status=WebsiteStatus(status_raw),
    )
    lead.primary_email = _row_to_optional_str(row.get("primary_email"))
    lead.all_emails = _row_to_list(row.get("all_emails"))
    lead.primary_phone = _row_to_optional_str(row.get("primary_phone"))
    lead.all_phones = _row_to_list(row.get("all_phones"))
    lead.whatsapp_links = _row_to_list(row.get("whatsapp_links"))
    lead.messenger_links = _row_to_list(row.get("messenger_links"))
    lead.booking_links = _row_to_list(row.get("booking_links"))
    lead.contact_form_urls = _row_to_list(row.get("contact_form_urls"))
    lead.primary_contact_method = _row_to_optional_str(row.get("primary_contact_method"))
    lead.guessed_email = _row_to_optional_str(row.get("guessed_email"))
    lead.issues_found = _row_to_list(row.get("issues_found"))
    lead.improvement_opportunities = _row_to_list(row.get("improvement_opportunities"))
    lead.outreach_angle = _row_to_optional_str(row.get("outreach_angle")) or ""
    lead.short_pitch = _row_to_optional_str(row.get("short_pitch")) or ""
    lead.contact_provenance = _row_contact_provenance(row)
    lead.email_eligibility = _row_to_optional_str(row.get("email_eligibility"))
    lead.email_eligibility_reason = _row_to_optional_str(row.get("email_eligibility_reason"))
    lead.outreach_policy_decision = _row_to_optional_str(row.get("outreach_policy_decision"))
    lead.outreach_policy_reason = _row_to_optional_str(row.get("outreach_policy_reason"))
    lead.outreach_policy_version = _row_to_optional_str(row.get("outreach_policy_version"))
    lead.offer_type = _row_to_optional_str(row.get("offer_type"))
    lead.email_subject = _row_to_optional_str(row.get("email_subject"))
    lead.email_opening = _row_to_optional_str(row.get("email_opening"))
    lead.email_cta = _row_to_optional_str(row.get("email_cta"))
    lead.email_body_preview = _row_to_optional_str(row.get("email_body_preview"))
    return lead


def _sendability_reason(row: pd.Series) -> str:
    if bool(row.get("suppressed", False)):
        return f"Suppressed: {_row_to_optional_str(row.get('suppression_reason')) or 'suppression list'}"
    if _row_to_optional_str(row.get("email_eligibility")) == "blocked":
        return _row_to_optional_str(row.get("email_eligibility_reason")) or "Blocked"
    if _row_to_optional_str(row.get("outreach_policy_decision")) == "blocked":
        return _row_to_optional_str(row.get("outreach_policy_reason")) or "Blocked by policy"
    if _row_to_optional_str(row.get("outreach_policy_decision")) == "review_required":
        return _row_to_optional_str(row.get("outreach_policy_reason")) or "Policy review required"
    if _row_to_optional_str(row.get("approval_state")) != "approved":
        return "Needs approval"
    return "Sendable"


def enrich_for_outreach(df: pd.DataFrame, store: OutreachStore) -> pd.DataFrame:
    """Merge mutable outreach state from SQLite into the static leads dataset."""
    if df.empty:
        return df.copy()

    enriched = df.copy()
    enriched["lead_id"] = enriched.apply(
        lambda row: stable_lead_id(_row_to_business_lead(row)),
        axis=1,
    )

    suppressions = {
        (str(item["channel"]), str(item["contact_value"])): item
        for item in store.list_suppressions()
    }
    items_by_lead: dict[str, dict] = {}
    for campaign in store.list_campaigns():
        for item in store.list_campaign_items(campaign["campaign_id"]):
            items_by_lead[item["lead_id"]] = item

    def _contact_email(row: pd.Series) -> str | None:
        return (
            _row_to_optional_str(row.get("primary_email"))
            or _row_to_optional_str(row.get("email"))
            or _row_to_optional_str(row.get("guessed_email"))
        )

    enriched["outreach_email"] = enriched.apply(_contact_email, axis=1)
    enriched["email_provenance"] = enriched.get("contact_provenance.email", pd.Series(index=enriched.index)).fillna("")
    enriched["suppression_reason"] = ""
    enriched["suppressed"] = False
    enriched["campaign_id"] = ""
    enriched["approval_state"] = ""
    enriched["campaign_item_id"] = ""
    enriched["approved_by"] = ""
    enriched["approved_at"] = ""

    for idx, row in enriched.iterrows():
        email = row.get("outreach_email")
        suppression = suppressions.get(("email", str(email))) if email else None
        if suppression:
            enriched.at[idx, "suppressed"] = True
            enriched.at[idx, "suppression_reason"] = suppression.get("reason", "")
        item = items_by_lead.get(str(row.get("lead_id")))
        if item:
            enriched.at[idx, "campaign_id"] = item.get("campaign_id", "")
            enriched.at[idx, "approval_state"] = item.get("state", "")
            enriched.at[idx, "campaign_item_id"] = item.get("item_id", "")
            enriched.at[idx, "approved_by"] = item.get("approved_by", "") or ""
            enriched.at[idx, "approved_at"] = item.get("approved_at", "") or ""

    enriched["sendability_reason"] = enriched.apply(_sendability_reason, axis=1)
    return enriched


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


def _render_outreach_workspace(outreach_df: pd.DataFrame, store: OutreachStore) -> None:
    """Render the outreach-focused review and campaign operations workspace."""
    st.subheader("Email-First Outreach Workspace")

    if outreach_df.empty:
        st.info("No leads available for outreach review with the current filters.")
        return

    total = len(outreach_df)
    allowed = int((outreach_df["email_eligibility"] == "allowed").sum()) if "email_eligibility" in outreach_df.columns else 0
    review_required = int((outreach_df["email_eligibility"] == "review_required").sum()) if "email_eligibility" in outreach_df.columns else 0
    blocked = int((outreach_df["email_eligibility"] == "blocked").sum()) if "email_eligibility" in outreach_df.columns else 0
    approved = int((outreach_df["approval_state"] == "approved").sum()) if "approval_state" in outreach_df.columns else 0

    metric_cols = st.columns(5)
    metric_cols[0].metric("Candidates", f"{total:,}")
    metric_cols[1].metric("Allowed", f"{allowed:,}")
    metric_cols[2].metric("Review Required", f"{review_required:,}")
    metric_cols[3].metric("Blocked", f"{blocked:,}")
    metric_cols[4].metric("Approved", f"{approved:,}")

    workspace = outreach_df.copy()
    sendable_mask = (
        (workspace.get("email_eligibility") == "allowed")
        & (workspace.get("outreach_policy_decision") == "allowed")
        & (~workspace.get("suppressed", False))
    )
    workspace = workspace[workspace["outreach_email"].notna()].copy()
    workspace["sendable_now"] = sendable_mask.loc[workspace.index]

    display_cols = [
        "company_name",
        "niche",
        "city",
        "country",
        "outreach_email",
        "email_provenance",
        "email_eligibility",
        "outreach_policy_decision",
        "suppressed",
        "approval_state",
        "offer_type",
        "sendability_reason",
        "campaign_id",
    ]
    display = workspace[[col for col in display_cols if col in workspace.columns]].rename(
        columns={
            "company_name": "Company",
            "niche": "Niche",
            "city": "City",
            "country": "Country",
            "outreach_email": "Email",
            "email_provenance": "Provenance",
            "email_eligibility": "Eligibility",
            "outreach_policy_decision": "Policy",
            "suppressed": "Suppressed",
            "approval_state": "Approval",
            "offer_type": "Offer",
            "sendability_reason": "Sendability Reason",
            "campaign_id": "Campaign",
        }
    )
    st.dataframe(display, width="stretch", hide_index=True)

    control_col, campaign_col = st.columns([1.3, 1.0])
    with control_col:
        st.markdown("#### Draft Review")
        company_options = [
            f"{row.company_name} | {row.city} | {row.outreach_email}"
            for row in workspace.itertuples(index=False)
        ]
        if not company_options:
            st.info("No outreach-usable email rows after filtering.")
            return

        selected_label = st.selectbox("Lead", options=company_options, key="outreach_selected_label")
        selected_row = workspace.iloc[company_options.index(selected_label)]
        selected_lead = _row_to_business_lead(selected_row)

        st.caption(selected_row.get("sendability_reason", ""))
        st.write(f"**Eligibility:** {selected_row.get('email_eligibility', '—')}")
        st.write(f"**Policy:** {selected_row.get('outreach_policy_decision', '—')} — {selected_row.get('outreach_policy_reason', '—')}")
        st.write(f"**Provenance:** {selected_row.get('email_provenance', '—')}")
        st.write(f"**Suppression:** {'yes' if bool(selected_row.get('suppressed', False)) else 'no'}")

        offer_override = st.selectbox(
            "Offer Type Override",
            options=["new-website", "website-improvement"],
            index=0 if selected_row.get("offer_type") == "new-website" else 1,
            key="outreach_offer_override",
        )
        st.markdown(f"**Subject:** {selected_row.get('email_subject', '—')}")
        st.markdown(f"**Opening:** {selected_row.get('email_opening', '—')}")
        st.markdown(f"**CTA:** {selected_row.get('email_cta', '—')}")
        st.text_area(
            "Body Preview",
            value=_row_to_optional_str(selected_row.get("email_body_preview")) or "",
            height=140,
            disabled=True,
            key="outreach_body_preview",
        )

        campaign_id = st.text_input("Campaign ID", value="campaign-review", key="outreach_campaign_id")
        actor = st.text_input("Operator", value="operator", key="outreach_actor")

        create_disabled = (
            selected_row.get("email_eligibility") != "allowed"
            or bool(selected_row.get("suppressed", False))
        )
        if st.button("Create Draft For Lead", disabled=create_disabled, key="outreach_create_draft"):
            create_campaign_draft(
                store,
                [selected_lead],
                campaign_id=campaign_id,
                created_by=actor,
                sender_profile=SenderProfile(profile_name="viewer-default"),
                execution_mode=CampaignExecutionMode.EXPORT_ONLY.value,
                title=campaign_id,
            )
            st.cache_data.clear()
            st.rerun()

        item_id = selected_row.get("campaign_item_id") or f"{campaign_id}:{selected_row.get('lead_id')}"
        approve_disabled = (
            selected_row.get("email_eligibility") != "allowed"
            or bool(selected_row.get("suppressed", False))
        )
        if st.button("Approve Draft", disabled=approve_disabled, key="outreach_approve"):
            approve_campaign_item(
                store,
                item_id,
                actor=actor,
                lead=selected_lead,
                offer_type=offer_override,
            )
            st.cache_data.clear()
            st.rerun()

        suppression_reason = st.text_input("Manual Suppression Reason", value="manual review", key="outreach_suppression_reason")
        if st.button("Suppress Email", key="outreach_suppress") and selected_row.get("outreach_email"):
            manually_suppress_contact(
                store,
                actor=actor,
                channel="email",
                contact_value=str(selected_row.get("outreach_email")),
                reason=suppression_reason,
                lead_id=str(selected_row.get("lead_id")),
            )
            st.cache_data.clear()
            st.rerun()

    with campaign_col:
        st.markdown("#### Campaign Actions")
        campaigns = store.list_campaigns()
        campaign_options = [item["campaign_id"] for item in campaigns] or [campaign_id]
        selected_campaign = st.selectbox(
            "Campaign",
            options=campaign_options,
            index=campaign_options.index(campaign_id) if campaign_id in campaign_options else 0,
            key="outreach_selected_campaign",
        )
        campaign_items = store.list_campaign_items(selected_campaign)
        approved_items = [item for item in campaign_items if item.get("state") == "approved"]

        sender_profile = SenderProfile(
            profile_name=st.text_input("Sender Profile", value="default", key="outreach_sender_profile"),
            mode=st.selectbox(
                "Execution Mode",
                options=[
                    CampaignExecutionMode.DRY_RUN.value,
                    CampaignExecutionMode.EXPORT_ONLY.value,
                    CampaignExecutionMode.DIRECT_SEND.value,
                ],
                index=1,
                key="outreach_mode",
            ),
            from_name=st.text_input("From Name", value="", key="outreach_from_name") or None,
            from_email=st.text_input("From Email", value="", key="outreach_from_email") or None,
            reply_to=st.text_input("Reply-To", value="", key="outreach_reply_to") or None,
            smtp_host=st.text_input("SMTP Host", value="", key="outreach_smtp_host") or None,
            smtp_username=st.text_input("SMTP Username", value="", key="outreach_smtp_username") or None,
            smtp_password=st.text_input("SMTP Password", value="", type="password", key="outreach_smtp_password") or None,
            daily_send_limit=int(st.number_input("Daily Send Limit", min_value=1, value=50, step=1, key="outreach_daily_cap")),
        )
        export_dir = st.text_input("Export Directory", value=DEFAULT_OUTREACH_EXPORT_DIR, key="outreach_export_dir")

        preflight_ok, missing = preflight_sender_profile(sender_profile, mode=sender_profile.mode)
        st.caption(
            "Direct-send preflight: "
            + ("ready" if preflight_ok else f"missing {', '.join(missing)}")
        )
        st.write(f"Approved items in batch: {len(approved_items)}")

        execute_disabled = (
            not approved_items
            or (
                sender_profile.mode == CampaignExecutionMode.DIRECT_SEND.value
                and not preflight_ok
            )
        )
        if st.button("Execute Campaign", disabled=execute_disabled, key="outreach_execute"):
            result = execute_campaign(
                store,
                selected_campaign,
                actor=actor,
                sender_profile=sender_profile,
                mode=sender_profile.mode,
                output_dir=export_dir,
            )
            if result.get("ok"):
                st.success(str(result))
            else:
                st.warning(str(result))
            st.cache_data.clear()
            st.rerun()

        st.markdown("#### Feedback & Outcomes")
        if campaign_items:
            item_options = [item["item_id"] for item in campaign_items]
            feedback_item_id = st.selectbox("Campaign Item", options=item_options, key="outreach_feedback_item")
            feedback_outcome = st.selectbox(
                "Outcome",
                options=["reply", "bounce", "opt_out", "failed"],
                key="outreach_feedback_outcome",
            )
            feedback_note = st.text_input("Outcome Note", value="", key="outreach_feedback_note")
            if st.button("Record Outcome", key="outreach_record_outcome"):
                record_campaign_feedback(
                    store,
                    feedback_item_id,
                    actor=actor,
                    outcome=feedback_outcome,
                    note=feedback_note,
                )
                st.cache_data.clear()
                st.rerun()

            audit_events = store.list_audit_events(entity_type="campaign", entity_id=selected_campaign)[:10]
            if audit_events:
                st.markdown("#### Recent Audit Events")
                for event in audit_events:
                    st.write(f"{event['created_at']} — {event['event_type']} — {event['actor']}")


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
    outreach_db_path = st.sidebar.text_input("Outreach DB", value=DEFAULT_OUTREACH_DB, key="_outreach_db_input")

    # --- Load ---
    p = Path(data_path)
    if not p.exists():
        st.error(f"File not found: `{data_path}`\n\nMake sure the pipeline has run and produced output.")
        st.stop()

    df = load_leads(data_path)
    store = load_outreach_store(outreach_db_path)
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
    outreach_df = enrich_for_outreach(filtered, store)
    outreach_count = len(outreach_df[outreach_df["outreach_email"].notna()]) if "outreach_email" in outreach_df.columns else 0

    tab_all, tab_reachable, tab_outreach = st.tabs([
        "All Leads",
        f"Reachable Leads ({reachable_count})",
        f"Outreach Workspace ({outreach_count})",
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

    with tab_outreach:
        _render_outreach_workspace(outreach_df, store)


if __name__ == "__main__":
    main()
