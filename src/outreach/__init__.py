"""Outreach workflow helpers for email-first campaign operations."""

from .generation import (
    derive_offer_type,
    generate_email_subject,
    generate_email_opening,
    generate_email_cta,
    generate_email_body_preview,
)
from .models import (
    AuditEvent,
    CampaignItem,
    CampaignRecord,
    EligibilityDecision,
    ExportOnlyResult,
    SenderProfile,
    SuppressionEntry,
)
from .policy import (
    DEFAULT_POLICY_VERSION,
    build_contact_provenance,
    classify_email_eligibility,
    infer_contact_provenance,
    load_policy_config,
    policy_decision_for_email,
)
from .sender import preflight_sender_profile, render_campaign_email, send_via_smtp
from .store import OutreachStore, stable_lead_id
from .workflow import (
    approve_campaign_item,
    campaign_item_from_lead,
    create_campaign_draft,
    evidence_snapshot_for_lead,
    execute_campaign,
    lead_email_for_outreach,
    load_sender_profile,
    manually_suppress_contact,
    record_campaign_feedback,
    render_draft_fields,
    resolve_outreach_store,
)

__all__ = [
    "AuditEvent",
    "CampaignItem",
    "CampaignRecord",
    "EligibilityDecision",
    "SenderProfile",
    "SuppressionEntry",
    "OutreachStore",
    "stable_lead_id",
    "DEFAULT_POLICY_VERSION",
    "build_contact_provenance",
    "classify_email_eligibility",
    "infer_contact_provenance",
    "load_policy_config",
    "policy_decision_for_email",
    "derive_offer_type",
    "generate_email_subject",
    "generate_email_opening",
    "generate_email_cta",
    "generate_email_body_preview",
    "ExportOnlyResult",
    "preflight_sender_profile",
    "render_campaign_email",
    "send_via_smtp",
    "approve_campaign_item",
    "campaign_item_from_lead",
    "create_campaign_draft",
    "evidence_snapshot_for_lead",
    "execute_campaign",
    "lead_email_for_outreach",
    "load_sender_profile",
    "manually_suppress_contact",
    "record_campaign_feedback",
    "render_draft_fields",
    "resolve_outreach_store",
]
