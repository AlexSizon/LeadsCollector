"""Workflow helpers for drafting, approving, and executing outreach campaigns."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from ..enums import CampaignExecutionMode, CampaignItemState, OfferType, PolicyDecision
from .generation import (
    generate_email_body_preview,
    generate_email_cta,
    generate_email_opening,
    generate_email_subject,
)
from .models import AuditEvent, CampaignItem, CampaignRecord, SenderProfile, SuppressionEntry, utc_now_iso
from .sender import preflight_sender_profile, send_via_smtp, sender_profile_to_dict
from .store import OutreachStore, stable_lead_id


def load_sender_profile(config: Dict[str, Any]) -> SenderProfile:
    """Build a sender profile from config with conservative defaults."""
    raw = dict(config.get("outreach_sender_profile") or {})
    raw.setdefault("mode", config.get("outreach_execution_mode", CampaignExecutionMode.EXPORT_ONLY.value))
    raw.setdefault("daily_send_limit", int(config.get("outreach_daily_send_limit", 50) or 50))
    raw.setdefault("policy_version", config.get("outreach_policy_version", "strict-email-first-v1"))
    return SenderProfile(**raw)


def resolve_outreach_store(config: Dict[str, Any]) -> OutreachStore:
    """Create the local outreach store configured for this workspace."""
    db_path = config.get("outreach_store_path", "data/outreach.db")
    return OutreachStore(db_path)


def lead_email_for_outreach(lead) -> Optional[str]:
    """Return the email channel that should be used for email-first drafts."""
    if getattr(lead, "primary_email", None):
        return str(lead.primary_email)
    if getattr(lead, "email", None):
        return str(lead.email)
    return None


def evidence_snapshot_for_lead(lead) -> Dict[str, Any]:
    """Persist the exact evidence used to support a campaign item."""
    return {
        "company_name": getattr(lead, "company_name", ""),
        "city": getattr(lead, "city", ""),
        "country": getattr(lead, "country", ""),
        "niche": getattr(lead, "niche", ""),
        "website_status": getattr(getattr(lead, "website_status", None), "value", getattr(lead, "website_status", None)),
        "issues_found": list(getattr(lead, "issues_found", []) or []),
        "outreach_angle": getattr(lead, "outreach_angle", ""),
        "short_pitch": getattr(lead, "short_pitch", ""),
        "email_eligibility": getattr(lead, "email_eligibility", None),
        "email_eligibility_reason": getattr(lead, "email_eligibility_reason", None),
        "policy_decision": getattr(lead, "outreach_policy_decision", None),
        "policy_reason": getattr(lead, "outreach_policy_reason", None),
        "policy_version": getattr(lead, "outreach_policy_version", None),
        "contact_provenance": dict(getattr(lead, "contact_provenance", {}) or {}),
        "google_reviews_count": getattr(lead, "google_reviews_count", None),
        "google_rating": getattr(lead, "google_rating", None),
    }


def render_draft_fields(lead, *, offer_type: Optional[str] = None) -> Dict[str, str]:
    """Render final email draft fields for a lead, honoring an offer override."""
    original_offer = getattr(lead, "offer_type", None)
    effective_offer = offer_type or original_offer or OfferType.WEBSITE_IMPROVEMENT.value
    lead.offer_type = effective_offer
    try:
        return {
            "offer_type": effective_offer,
            "email_subject": generate_email_subject(lead),
            "email_opening": generate_email_opening(lead),
            "email_cta": generate_email_cta(lead),
            "email_body_preview": generate_email_body_preview(lead),
        }
    finally:
        lead.offer_type = original_offer


def campaign_item_from_lead(
    lead,
    *,
    campaign_id: str,
    offer_type: Optional[str] = None,
) -> CampaignItem:
    """Create a draft campaign item snapshot from one eligible lead."""
    email = lead_email_for_outreach(lead)
    if not email:
        raise ValueError("Lead has no direct email for outreach")
    rendered = render_draft_fields(lead, offer_type=offer_type)
    lead_id = stable_lead_id(lead)
    return CampaignItem(
        item_id=f"{campaign_id}:{lead_id}",
        campaign_id=campaign_id,
        lead_id=lead_id,
        company_name=getattr(lead, "company_name", "") or "",
        email=email,
        city=getattr(lead, "city", "") or "",
        country=getattr(lead, "country", "") or "",
        offer_type=rendered["offer_type"],
        rendered_subject=rendered["email_subject"],
        rendered_opening=rendered["email_opening"],
        rendered_cta=rendered["email_cta"],
        rendered_body_preview=rendered["email_body_preview"],
        evidence_snapshot=evidence_snapshot_for_lead(lead),
        state=CampaignItemState.DRAFT.value,
    )


def create_campaign_draft(
    store: OutreachStore,
    leads: Iterable[object],
    *,
    campaign_id: str,
    created_by: str,
    sender_profile: SenderProfile,
    execution_mode: str,
    title: str = "",
    notes: str = "",
) -> Dict[str, Any]:
    """Create a campaign and draft items for all eligible leads."""
    campaign = CampaignRecord(
        campaign_id=campaign_id,
        execution_mode=execution_mode,
        sender_profile=sender_profile.profile_name,
        created_by=created_by,
        title=title,
        notes=notes,
    )
    store.create_campaign(campaign)
    added = 0
    skipped: List[Dict[str, str]] = []
    for lead in leads:
        email = lead_email_for_outreach(lead)
        if getattr(lead, "email_eligibility", None) != "allowed":
            skipped.append(
                {
                    "company_name": getattr(lead, "company_name", "") or "",
                    "reason": getattr(lead, "email_eligibility_reason", None) or "not eligible",
                }
            )
            continue
        if not email:
            skipped.append(
                {
                    "company_name": getattr(lead, "company_name", "") or "",
                    "reason": "no direct email",
                }
            )
            continue
        if store.is_suppressed("email", email):
            skipped.append(
                {
                    "company_name": getattr(lead, "company_name", "") or "",
                    "reason": "contact is suppressed",
                }
            )
            continue
        item = campaign_item_from_lead(lead, campaign_id=campaign_id)
        store.add_campaign_item(item)
        added += 1
        store.record_audit(
            AuditEvent(
                event_type="draft_created",
                actor=created_by,
                entity_type="campaign_item",
                entity_id=item.item_id,
                payload={
                    "campaign_id": campaign_id,
                    "lead_id": item.lead_id,
                    "offer_type": item.offer_type,
                },
            )
        )
    store.record_audit(
        AuditEvent(
            event_type="campaign_created",
            actor=created_by,
            entity_type="campaign",
            entity_id=campaign_id,
            payload={
                "execution_mode": execution_mode,
                "sender_profile": sender_profile.profile_name,
                "draft_count": added,
                "skipped_count": len(skipped),
            },
        )
    )
    return {
        "campaign_id": campaign_id,
        "draft_count": added,
        "skipped": skipped,
    }


def approve_campaign_item(
    store: OutreachStore,
    item_id: str,
    *,
    actor: str,
    lead=None,
    offer_type: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Approve one draft, optionally applying a final offer override."""
    item = store.get_campaign_item(item_id)
    if item is None:
        return None
    if lead is not None and offer_type is not None:
        rendered = render_draft_fields(lead, offer_type=offer_type)
        evidence = evidence_snapshot_for_lead(lead)
        evidence["offer_type_override"] = offer_type
        store.update_campaign_item_render(
            item_id,
            offer_type=rendered["offer_type"],
            rendered_subject=rendered["email_subject"],
            rendered_opening=rendered["email_opening"],
            rendered_cta=rendered["email_cta"],
            rendered_body_preview=rendered["email_body_preview"],
            evidence_snapshot=evidence,
        )
    approved_at = utc_now_iso()
    store.update_campaign_item_state(
        item_id,
        CampaignItemState.APPROVED.value,
        approved_by=actor,
        approved_at=approved_at,
    )
    store.record_audit(
        AuditEvent(
            event_type="approved",
            actor=actor,
            entity_type="campaign_item",
            entity_id=item_id,
            payload={"approved_at": approved_at},
        )
    )
    return store.get_campaign_item(item_id)


def execute_campaign(
    store: OutreachStore,
    campaign_id: str,
    *,
    actor: str,
    sender_profile: SenderProfile,
    mode: str,
    output_dir: str | Path,
) -> Dict[str, Any]:
    """Execute a campaign in dry-run, export-only, or direct-send mode."""
    items = store.list_campaign_items(campaign_id)
    approved_items = [item for item in items if item.get("state") == CampaignItemState.APPROVED.value]
    if not approved_items:
        return {
            "ok": False,
            "campaign_id": campaign_id,
            "mode": mode,
            "reason": "no approved items",
        }

    preflight_ok, missing = preflight_sender_profile(sender_profile, mode=mode)
    if mode == CampaignExecutionMode.DIRECT_SEND.value and not preflight_ok:
        return {
            "ok": False,
            "campaign_id": campaign_id,
            "mode": mode,
            "reason": "preflight_failed",
            "missing": missing,
        }

    if mode == CampaignExecutionMode.DRY_RUN.value:
        store.record_audit(
            AuditEvent(
                event_type="dry_run",
                actor=actor,
                entity_type="campaign",
                entity_id=campaign_id,
                payload={
                    "item_count": len(approved_items),
                    "sender_profile": sender_profile.profile_name,
                },
            )
        )
        return {
            "ok": True,
            "campaign_id": campaign_id,
            "mode": mode,
            "item_count": len(approved_items),
            "sender_profile": sender_profile_to_dict(sender_profile),
        }

    if mode == CampaignExecutionMode.EXPORT_ONLY.value:
        result = store.export_campaign(
            campaign_id,
            output_dir,
            states=[CampaignItemState.APPROVED.value],
        )
        store.record_audit(
            AuditEvent(
                event_type="exported",
                actor=actor,
                entity_type="campaign",
                entity_id=campaign_id,
                payload=asdict(result),
            )
        )
        return {
            "ok": True,
            "campaign_id": campaign_id,
            "mode": mode,
            "item_count": result.item_count,
            "csv_path": result.csv_path,
            "json_path": result.json_path,
        }

    if mode == CampaignExecutionMode.DIRECT_SEND.value:
        sent_count = 0
        failed_count = 0
        transport_notes: List[str] = []
        for item in approved_items:
            try:
                transport_note = send_via_smtp(item, sender_profile)
                sent_at = utc_now_iso()
                store.update_campaign_item_state(
                    item["item_id"],
                    CampaignItemState.SENT.value,
                    sent_at=sent_at,
                    result_note=transport_note,
                )
                store.record_audit(
                    AuditEvent(
                        event_type="sent",
                        actor=actor,
                        entity_type="campaign_item",
                        entity_id=item["item_id"],
                        payload={"sent_at": sent_at, "transport": transport_note},
                    )
                )
                sent_count += 1
                transport_notes.append(transport_note)
            except Exception as exc:
                failed_count += 1
                store.update_campaign_item_state(
                    item["item_id"],
                    CampaignItemState.FAILED.value,
                    failure_reason=str(exc),
                )
                store.record_audit(
                    AuditEvent(
                        event_type="send_failed",
                        actor=actor,
                        entity_type="campaign_item",
                        entity_id=item["item_id"],
                        payload={"reason": str(exc)},
                    )
                )
        if sent_count > 0:
            store.record_audit(
                AuditEvent(
                    event_type="campaign_sent",
                    actor=actor,
                    entity_type="campaign",
                    entity_id=campaign_id,
                    payload={"sent_count": sent_count, "failed_count": failed_count},
                )
            )
        return {
            "ok": failed_count == 0 and sent_count > 0,
            "campaign_id": campaign_id,
            "mode": mode,
            "sent_count": sent_count,
            "failed_count": failed_count,
            "transport": transport_notes[0] if transport_notes else None,
            "reason": None if failed_count == 0 and sent_count > 0 else "partial_or_failed_send",
        }

    return {
        "ok": False,
        "campaign_id": campaign_id,
        "mode": mode,
        "reason": f"unsupported mode: {mode}",
    }


def record_campaign_feedback(
    store: OutreachStore,
    item_id: str,
    *,
    actor: str,
    outcome: str,
    note: str = "",
) -> Optional[Dict[str, Any]]:
    """Record reply, bounce, or opt-out outcomes and apply suppression."""
    item = store.get_campaign_item(item_id)
    if item is None:
        return None

    new_state = {
        "reply": CampaignItemState.REPLIED.value,
        "bounce": CampaignItemState.BOUNCED.value,
        "opt_out": CampaignItemState.OPTED_OUT.value,
        "failed": CampaignItemState.FAILED.value,
    }.get(outcome)
    if not new_state:
        raise ValueError(f"Unsupported outcome: {outcome}")

    store.update_campaign_item_state(
        item_id,
        new_state,
        failure_reason=note if new_state == CampaignItemState.FAILED.value else None,
        result_note=note or None,
    )

    if new_state in {CampaignItemState.BOUNCED.value, CampaignItemState.OPTED_OUT.value}:
        reason = "hard_bounce" if new_state == CampaignItemState.BOUNCED.value else "opt_out"
        store.add_suppression(
            SuppressionEntry(
                channel="email",
                contact_value=str(item.get("email") or ""),
                reason=reason,
                source=f"campaign:{item.get('campaign_id')}",
                lead_id=item.get("lead_id"),
            )
        )

    store.record_audit(
        AuditEvent(
            event_type=f"{outcome}_updated",
            actor=actor,
            entity_type="campaign_item",
            entity_id=item_id,
            payload={"state": new_state, "note": note},
        )
    )
    return store.get_campaign_item(item_id)


def manually_suppress_contact(
    store: OutreachStore,
    *,
    actor: str,
    channel: str,
    contact_value: str,
    reason: str,
    lead_id: Optional[str] = None,
) -> None:
    """Add a manual suppression entry and record an audit trail."""
    store.add_suppression(
        SuppressionEntry(
            channel=channel,
            contact_value=contact_value,
            reason=reason,
            source=f"manual:{actor}",
            lead_id=lead_id,
        )
    )
    store.record_audit(
        AuditEvent(
            event_type="manual_suppression",
            actor=actor,
            entity_type="suppression",
            entity_id=f"{channel}:{contact_value}",
            payload={"reason": reason, "lead_id": lead_id},
        )
    )
