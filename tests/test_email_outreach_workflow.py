from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from src.enums import CampaignExecutionMode, CampaignItemState, WebsiteStatus
from src.models import BusinessLead
from src.outreach import (
    OutreachStore,
    SenderProfile,
    approve_campaign_item,
    build_contact_provenance,
    classify_email_eligibility,
    create_campaign_draft,
    execute_campaign,
    manually_suppress_contact,
    record_campaign_feedback,
    resolve_outreach_store,
)


def _lead(
    *,
    company_name: str = "Sample Co",
    website_status: WebsiteStatus = WebsiteStatus.NO_WEBSITE,
    primary_email: str | None = None,
    guessed_email: str | None = None,
    country: str = "Spain",
) -> BusinessLead:
    lead = BusinessLead(
        company_name=company_name,
        niche="restaurant",
        city="Madrid",
        country=country,
        website_url="https://sample.example" if website_status != WebsiteStatus.NO_WEBSITE else None,
    )
    lead.website_status = website_status
    lead.primary_email = primary_email
    lead.email = primary_email
    lead.guessed_email = guessed_email
    lead.outreach_angle = "Observed evidence."
    lead.short_pitch = "A concise factual pitch."
    lead.contact_provenance = build_contact_provenance(lead)
    eligibility, reason, policy_decision, policy_reason, policy_version = classify_email_eligibility(lead)
    lead.email_eligibility = eligibility.value
    lead.email_eligibility_reason = reason
    lead.outreach_policy_decision = policy_decision.value
    lead.outreach_policy_reason = policy_reason
    lead.outreach_policy_version = policy_version
    lead.offer_type = "new-website" if website_status == WebsiteStatus.NO_WEBSITE else "website-improvement"
    lead.email_subject = f"{company_name}: website idea"
    lead.email_opening = "I noticed a few factual signals."
    lead.email_cta = "If useful, I can share a quick outline."
    lead.email_body_preview = f"{lead.email_opening} {lead.short_pitch} {lead.email_cta}"
    return lead


def test_scraped_email_is_allowed_and_guessed_email_is_blocked():
    direct = _lead(primary_email="hello@sample.example")
    guessed = _lead(primary_email=None, guessed_email="owner@sample.example")

    direct_decision = classify_email_eligibility(direct)
    guessed_decision = classify_email_eligibility(guessed)

    assert direct_decision[0].value == "allowed"
    assert direct_decision[2].value == "allowed"
    assert guessed.contact_provenance["email"] == "guessed"
    assert guessed_decision[0].value == "blocked"
    assert "guessed-only" in guessed_decision[1]


def test_manual_suppression_blocks_future_eligibility(tmp_path):
    store = OutreachStore(tmp_path / "outreach.db")
    lead = _lead(primary_email="hello@sample.example")

    manually_suppress_contact(
        store,
        actor="alice",
        channel="email",
        contact_value="hello@sample.example",
        reason="manual hold",
        lead_id="lead:sample",
    )

    decision = classify_email_eligibility(lead, suppressed=store.is_suppressed("email", "hello@sample.example"))
    assert decision[0].value == "blocked"
    assert decision[2].value == "blocked"
    assert store.list_suppressions()[0]["reason"] == "manual hold"


def test_suppressed_contact_is_skipped_during_draft_creation(tmp_path):
    store = OutreachStore(tmp_path / "outreach.db")
    sender = SenderProfile(
        profile_name="ops",
        mode=CampaignExecutionMode.EXPORT_ONLY.value,
        from_email="hello@example.com",
        reply_to="reply@example.com",
    )
    lead = _lead(primary_email="hello@sample.example")
    manually_suppress_contact(
        store,
        actor="alice",
        channel="email",
        contact_value="hello@sample.example",
        reason="manual hold",
        lead_id="lead:sample",
    )

    result = create_campaign_draft(
        store,
        [lead],
        campaign_id="camp-suppressed",
        created_by="alice",
        sender_profile=sender,
        execution_mode=CampaignExecutionMode.EXPORT_ONLY.value,
    )

    assert result["draft_count"] == 0
    assert result["skipped"][0]["reason"] == "contact is suppressed"
    assert store.list_campaign_items("camp-suppressed") == []


def test_campaign_draft_export_and_feedback_flow(tmp_path):
    store = OutreachStore(tmp_path / "outreach.db")
    sender = SenderProfile(
        profile_name="ops",
        mode=CampaignExecutionMode.EXPORT_ONLY.value,
        from_email="hello@example.com",
        reply_to="reply@example.com",
    )
    lead = _lead(primary_email="hello@sample.example")
    second_lead = _lead(company_name="Second Co", primary_email="info@second.example")

    result = create_campaign_draft(
        store,
        [lead, second_lead],
        campaign_id="camp-001",
        created_by="alice",
        sender_profile=sender,
        execution_mode=CampaignExecutionMode.EXPORT_ONLY.value,
        title="Initial batch",
    )
    assert result["draft_count"] == 2

    item_id = store.list_campaign_items("camp-001")[0]["item_id"]
    store.update_campaign_item_state(
        item_id,
        CampaignItemState.APPROVED.value,
        approved_by="alice",
        approved_at="2026-03-20T00:00:00+00:00",
    )

    execution = execute_campaign(
        store,
        "camp-001",
        actor="alice",
        sender_profile=sender,
        mode=CampaignExecutionMode.EXPORT_ONLY.value,
        output_dir=tmp_path / "exports",
    )
    assert execution["ok"] is True
    assert execution["item_count"] == 1
    assert Path(execution["csv_path"]).exists()
    assert Path(execution["json_path"]).exists()

    updated = record_campaign_feedback(
        store,
        item_id,
        actor="alice",
        outcome="bounce",
        note="550 user unknown",
    )
    assert updated is not None
    assert updated["state"] == CampaignItemState.BOUNCED.value
    assert store.is_suppressed("email", "hello@sample.example") is True


def test_approval_can_override_offer_type(tmp_path):
    store = OutreachStore(tmp_path / "outreach.db")
    sender = SenderProfile(
        profile_name="ops",
        mode=CampaignExecutionMode.EXPORT_ONLY.value,
        from_email="hello@example.com",
        reply_to="reply@example.com",
    )
    lead = _lead(primary_email="hello@sample.example", website_status=WebsiteStatus.BROKEN_WEBSITE)

    create_campaign_draft(
        store,
        [lead],
        campaign_id="camp-override",
        created_by="alice",
        sender_profile=sender,
        execution_mode=CampaignExecutionMode.EXPORT_ONLY.value,
    )
    item_id = store.list_campaign_items("camp-override")[0]["item_id"]
    approved = approve_campaign_item(
        store,
        item_id,
        actor="alice",
        lead=lead,
        offer_type="new-website",
    )

    assert approved is not None
    assert approved["state"] == CampaignItemState.APPROVED.value
    assert approved["offer_type"] == "new-website"
    assert approved["approved_by"] == "alice"


def test_direct_send_requires_preflight(tmp_path):
    store = OutreachStore(tmp_path / "outreach.db")
    sender = SenderProfile(profile_name="ops", mode=CampaignExecutionMode.DIRECT_SEND.value)
    lead = _lead(primary_email="hello@sample.example")

    create_campaign_draft(
        store,
        [lead],
        campaign_id="camp-002",
        created_by="alice",
        sender_profile=sender,
        execution_mode=CampaignExecutionMode.DIRECT_SEND.value,
    )
    item_id = store.list_campaign_items("camp-002")[0]["item_id"]
    store.update_campaign_item_state(
        item_id,
        CampaignItemState.APPROVED.value,
        approved_by="alice",
        approved_at="2026-03-20T00:00:00+00:00",
    )

    result = execute_campaign(
        store,
        "camp-002",
        actor="alice",
        sender_profile=sender,
        mode=CampaignExecutionMode.DIRECT_SEND.value,
        output_dir=tmp_path / "exports",
    )
    assert result["ok"] is False
    assert result["reason"] == "preflight_failed"
    assert "from_email" in result["missing"]


def test_direct_send_marks_items_sent_when_smtp_succeeds(tmp_path):
    store = OutreachStore(tmp_path / "outreach.db")
    sender = SenderProfile(
        profile_name="ops",
        mode=CampaignExecutionMode.DIRECT_SEND.value,
        from_email="hello@example.com",
        from_name="Alex",
        reply_to="reply@example.com",
        smtp_host="smtp.example.com",
        smtp_username="alex",
        smtp_password="secret",
    )
    lead = _lead(primary_email="hello@sample.example")

    create_campaign_draft(
        store,
        [lead],
        campaign_id="camp-send",
        created_by="alice",
        sender_profile=sender,
        execution_mode=CampaignExecutionMode.DIRECT_SEND.value,
    )
    item_id = store.list_campaign_items("camp-send")[0]["item_id"]
    store.update_campaign_item_state(
        item_id,
        CampaignItemState.APPROVED.value,
        approved_by="alice",
        approved_at="2026-03-20T00:00:00+00:00",
    )

    smtp_client = MagicMock()
    smtp_context = MagicMock()
    smtp_context.__enter__.return_value = smtp_client
    smtp_context.__exit__.return_value = None

    with patch("src.outreach.sender.smtplib.SMTP", return_value=smtp_context):
        result = execute_campaign(
            store,
            "camp-send",
            actor="alice",
            sender_profile=sender,
            mode=CampaignExecutionMode.DIRECT_SEND.value,
            output_dir=tmp_path / "exports",
        )

    updated = store.get_campaign_item(item_id)
    assert result["ok"] is True
    assert result["sent_count"] == 1
    assert result["failed_count"] == 0
    assert updated is not None
    assert updated["state"] == CampaignItemState.SENT.value
    assert updated["sent_at"]
    assert updated["result_note"] == "smtp:smtp.example.com:587"
    smtp_client.send_message.assert_called_once()


def test_direct_send_marks_items_failed_when_smtp_errors(tmp_path):
    store = OutreachStore(tmp_path / "outreach.db")
    sender = SenderProfile(
        profile_name="ops",
        mode=CampaignExecutionMode.DIRECT_SEND.value,
        from_email="hello@example.com",
        reply_to="reply@example.com",
        smtp_host="smtp.example.com",
        smtp_username="alex",
        smtp_password="secret",
    )
    lead = _lead(primary_email="hello@sample.example")

    create_campaign_draft(
        store,
        [lead],
        campaign_id="camp-send-fail",
        created_by="alice",
        sender_profile=sender,
        execution_mode=CampaignExecutionMode.DIRECT_SEND.value,
    )
    item_id = store.list_campaign_items("camp-send-fail")[0]["item_id"]
    store.update_campaign_item_state(
        item_id,
        CampaignItemState.APPROVED.value,
        approved_by="alice",
        approved_at="2026-03-20T00:00:00+00:00",
    )

    smtp_client = MagicMock()
    smtp_client.send_message.side_effect = RuntimeError("smtp transport failed")
    smtp_context = MagicMock()
    smtp_context.__enter__.return_value = smtp_client
    smtp_context.__exit__.return_value = None

    with patch("src.outreach.sender.smtplib.SMTP", return_value=smtp_context):
        result = execute_campaign(
            store,
            "camp-send-fail",
            actor="alice",
            sender_profile=sender,
            mode=CampaignExecutionMode.DIRECT_SEND.value,
            output_dir=tmp_path / "exports",
        )

    updated = store.get_campaign_item(item_id)
    assert result["ok"] is False
    assert result["sent_count"] == 0
    assert result["failed_count"] == 1
    assert result["reason"] == "partial_or_failed_send"
    assert updated is not None
    assert updated["state"] == CampaignItemState.FAILED.value
    assert updated["failure_reason"] == "smtp transport failed"


def test_resolve_outreach_store_uses_configured_path(tmp_path):
    store = resolve_outreach_store({"outreach_store_path": str(tmp_path / "nested" / "ops.db")})
    assert store.db_path == tmp_path / "nested" / "ops.db"
    assert store.db_path.exists()
