"""Eligibility and policy helpers for email-first outreach."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from ..enums import ContactProvenance, OutreachEligibility, PolicyDecision

DEFAULT_POLICY_VERSION = "strict-email-first-v1"
_DEFAULT_POLICY: Dict[str, Any] = {
    "version": DEFAULT_POLICY_VERSION,
    "default": {
        "email": {
            ContactProvenance.SCRAPED.value: PolicyDecision.ALLOWED.value,
            ContactProvenance.JSON_LD.value: PolicyDecision.ALLOWED.value,
            ContactProvenance.SOCIAL.value: PolicyDecision.REVIEW_REQUIRED.value,
            ContactProvenance.GUESSED.value: PolicyDecision.BLOCKED.value,
            ContactProvenance.MANUAL.value: PolicyDecision.REVIEW_REQUIRED.value,
            ContactProvenance.UNKNOWN.value: PolicyDecision.REVIEW_REQUIRED.value,
        }
    },
    "countries": {},
}


def load_policy_config(path: Optional[str]) -> Dict[str, Any]:
    """Load outreach policy config from disk or return the built-in default."""
    if not path:
        return dict(_DEFAULT_POLICY)

    p = Path(path)
    if not p.exists():
        return dict(_DEFAULT_POLICY)

    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return dict(_DEFAULT_POLICY)

    if not isinstance(data, dict):
        return dict(_DEFAULT_POLICY)
    if "version" not in data:
        data["version"] = DEFAULT_POLICY_VERSION
    if "default" not in data:
        data["default"] = _DEFAULT_POLICY["default"]
    return data


def infer_contact_provenance(lead) -> str:
    """Infer the email provenance for a lead from its available fields."""
    lead_provenance = getattr(lead, "contact_provenance", {}) or {}
    if isinstance(lead_provenance, dict):
        email_provenance = lead_provenance.get("email")
        if email_provenance:
            return str(email_provenance)
    if getattr(lead, "primary_email", None) or getattr(lead, "email", None):
        return ContactProvenance.SCRAPED.value
    if getattr(lead, "guessed_email", None):
        return ContactProvenance.GUESSED.value
    if getattr(lead, "lead_source", "") in {"instagram", "facebook"}:
        return ContactProvenance.SOCIAL.value
    return ContactProvenance.UNKNOWN.value


def build_contact_provenance(lead, *, jld: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    """Build per-channel provenance annotations for outreach review."""
    provenance: Dict[str, str] = {}
    jld = jld or {}
    jld_email = str(jld.get("email") or "").strip().lower()
    jld_phone = str(jld.get("phone") or "").strip()
    lead_source = str(getattr(lead, "lead_source", "") or "").lower()

    direct_emails = [
        str(value).strip().lower()
        for value in (
            getattr(lead, "primary_email", None),
            getattr(lead, "email", None),
        )
        if value
    ]
    if direct_emails:
        if jld_email and jld_email in direct_emails:
            provenance["email"] = ContactProvenance.JSON_LD.value
        elif lead_source in {"instagram", "facebook"} and not getattr(lead, "website_url", None):
            provenance["email"] = ContactProvenance.SOCIAL.value
        else:
            provenance["email"] = ContactProvenance.SCRAPED.value
    elif getattr(lead, "guessed_email", None):
        provenance["email"] = ContactProvenance.GUESSED.value

    phones = [
        str(value).strip()
        for value in (
            getattr(lead, "primary_phone", None),
            getattr(lead, "phone", None),
        )
        if value
    ]
    if phones:
        if jld_phone and jld_phone in phones:
            provenance["phone"] = ContactProvenance.JSON_LD.value
        elif lead_source in {"instagram", "facebook"} and not getattr(lead, "website_url", None):
            provenance["phone"] = ContactProvenance.SOCIAL.value
        else:
            provenance["phone"] = ContactProvenance.SCRAPED.value

    if getattr(lead, "whatsapp_links", None):
        provenance["whatsapp"] = ContactProvenance.SCRAPED.value
    elif getattr(lead, "whatsapp_url", None):
        provenance["whatsapp"] = ContactProvenance.SOCIAL.value

    if getattr(lead, "messenger_links", None):
        provenance["messenger"] = ContactProvenance.SCRAPED.value
    elif getattr(lead, "facebook_url", None):
        provenance["messenger"] = ContactProvenance.SOCIAL.value

    if getattr(lead, "contact_form_urls", None):
        provenance["contact_form"] = ContactProvenance.SCRAPED.value
    if getattr(lead, "booking_links", None):
        provenance["booking"] = ContactProvenance.SCRAPED.value

    return provenance


def policy_decision_for_email(
    country: str,
    provenance: str,
    policy: Optional[Dict[str, Any]] = None,
) -> Tuple[PolicyDecision, str, str]:
    """Return policy decision, human-readable reason, and version for email use."""
    cfg = policy or dict(_DEFAULT_POLICY)
    version = str(cfg.get("version") or DEFAULT_POLICY_VERSION)
    country_rules = ((cfg.get("countries") or {}).get(country) or {}).get("email") or {}
    default_rules = ((cfg.get("default") or {}).get("email") or {})
    raw_decision = country_rules.get(provenance) or default_rules.get(provenance) or PolicyDecision.REVIEW_REQUIRED.value
    decision = PolicyDecision(raw_decision)
    if decision == PolicyDecision.ALLOWED:
        reason = f"{provenance} email allowed by policy"
    elif decision == PolicyDecision.BLOCKED:
        reason = f"{provenance} email blocked by policy"
    else:
        reason = f"{provenance} email requires review under policy"
    return decision, reason, version


def classify_email_eligibility(
    lead,
    *,
    policy: Optional[Dict[str, Any]] = None,
    suppressed: bool = False,
) -> Tuple[OutreachEligibility, str, PolicyDecision, str, str]:
    """Classify email eligibility and related policy data for one lead."""
    provenance = infer_contact_provenance(lead)
    decision, policy_reason, version = policy_decision_for_email(
        getattr(lead, "country", "") or "",
        provenance,
        policy=policy,
    )

    if suppressed:
        return (
            OutreachEligibility.BLOCKED,
            "contact is suppressed",
            PolicyDecision.BLOCKED,
            "contact is suppressed",
            version,
        )

    if provenance == ContactProvenance.GUESSED.value:
        return (
            OutreachEligibility.BLOCKED,
            "guessed-only email is blocked by default",
            decision,
            policy_reason,
            version,
        )

    if decision == PolicyDecision.BLOCKED:
        return (
            OutreachEligibility.BLOCKED,
            policy_reason,
            decision,
            policy_reason,
            version,
        )

    if decision == PolicyDecision.REVIEW_REQUIRED:
        return (
            OutreachEligibility.REVIEW_REQUIRED,
            policy_reason,
            decision,
            policy_reason,
            version,
        )

    if getattr(lead, "primary_email", None) or getattr(lead, "email", None):
        return (
            OutreachEligibility.ALLOWED,
            f"{provenance} business email available",
            decision,
            policy_reason,
            version,
        )

    return (
        OutreachEligibility.BLOCKED,
        "no direct email available",
        decision,
        policy_reason,
        version,
    )
