"""Domain models for email-first outreach workflow."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..enums import CampaignExecutionMode, CampaignItemState, OfferType, OutreachEligibility, PolicyDecision


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class EligibilityDecision:
    """Decision produced by outreach eligibility and policy checks."""

    eligibility: OutreachEligibility
    reason: str
    provenance: str
    policy_decision: PolicyDecision
    policy_reason: str
    policy_version: str

    @property
    def sendable(self) -> bool:
        return (
            self.eligibility == OutreachEligibility.ALLOWED
            and self.policy_decision == PolicyDecision.ALLOWED
        )


@dataclass
class SenderProfile:
    """Operator-owned sender configuration for export or direct send."""

    profile_name: str = "default"
    mode: str = CampaignExecutionMode.EXPORT_ONLY.value
    from_email: Optional[str] = None
    from_name: Optional[str] = None
    reply_to: Optional[str] = None
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    use_tls: bool = True
    daily_send_limit: int = 50
    policy_version: str = "strict-email-first-v1"


@dataclass
class CampaignRecord:
    """High-level outreach campaign metadata."""

    campaign_id: str
    execution_mode: str
    sender_profile: str
    created_by: str
    created_at: str = field(default_factory=utc_now_iso)
    title: str = ""
    notes: str = ""


@dataclass
class CampaignItem:
    """Per-lead campaign row stored in the outreach database."""

    item_id: str
    campaign_id: str
    lead_id: str
    company_name: str
    email: str
    city: str
    country: str
    offer_type: str
    rendered_subject: str
    rendered_opening: str
    rendered_cta: str
    rendered_body_preview: str
    evidence_snapshot: Dict[str, Any]
    state: str = CampaignItemState.DRAFT.value
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    sent_at: Optional[str] = None
    failure_reason: Optional[str] = None
    result_note: Optional[str] = None

    def snapshot_json(self) -> Dict[str, Any]:
        data = asdict(self)
        data["evidence_snapshot"] = dict(self.evidence_snapshot or {})
        return data


@dataclass
class SuppressionEntry:
    """A contact or lead entry that must not be contacted again."""

    channel: str
    contact_value: str
    reason: str
    source: str
    created_at: str = field(default_factory=utc_now_iso)
    lead_id: Optional[str] = None


@dataclass
class AuditEvent:
    """Audit event for outreach operations."""

    event_type: str
    actor: str
    entity_type: str
    entity_id: str
    created_at: str = field(default_factory=utc_now_iso)
    payload: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExportOnlyResult:
    """Export metadata returned by export-only execution."""

    campaign_id: str
    csv_path: str
    json_path: str
    item_count: int
    created_at: str = field(default_factory=utc_now_iso)
