"""Sender helpers for preflight and SMTP-backed direct-send execution."""

from __future__ import annotations

from dataclasses import asdict
from email.message import EmailMessage
import smtplib
from typing import Dict, List, Tuple

from .models import SenderProfile


def preflight_sender_profile(profile: SenderProfile, mode: str | None = None) -> Tuple[bool, List[str]]:
    """Validate whether a sender profile can be used for the requested mode."""
    effective_mode = mode or profile.mode
    missing: List[str] = []

    if not profile.from_email:
        missing.append("from_email")
    if not profile.reply_to:
        missing.append("reply_to")

    if effective_mode == "direct-send":
        if not profile.smtp_host:
            missing.append("smtp_host")
        if not profile.smtp_username:
            missing.append("smtp_username")
        if not profile.smtp_password:
            missing.append("smtp_password")

    return (len(missing) == 0, missing)


def sender_profile_to_dict(profile: SenderProfile) -> Dict[str, object]:
    """Serialize a sender profile for viewer or debugging output."""
    data = asdict(profile)
    if data.get("smtp_password"):
        data["smtp_password"] = "***"
    return data


def render_campaign_email(item: Dict[str, object], profile: SenderProfile) -> EmailMessage:
    """Build an SMTP-ready email message for one campaign item."""
    subject = str(item.get("rendered_subject") or "").strip()
    opening = str(item.get("rendered_opening") or "").strip()
    body_preview = str(item.get("rendered_body_preview") or "").strip()
    cta = str(item.get("rendered_cta") or "").strip()

    body_parts: List[str] = []
    if opening:
        body_parts.append(opening)
    if body_preview and body_preview != opening:
        body_parts.append(body_preview)
    if cta and cta not in body_preview:
        body_parts.append(cta)
    body = "\n\n".join(part for part in body_parts if part)

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = (
        f"{profile.from_name} <{profile.from_email}>"
        if profile.from_name and profile.from_email
        else (profile.from_email or "")
    )
    msg["To"] = str(item.get("email") or "").strip()
    if profile.reply_to:
        msg["Reply-To"] = profile.reply_to
    msg.set_content(body)
    return msg


def send_via_smtp(item: Dict[str, object], profile: SenderProfile) -> str:
    """Send one campaign item via SMTP and return a transport note."""
    message = render_campaign_email(item, profile)
    port = int(profile.smtp_port or 587)
    with smtplib.SMTP(profile.smtp_host, port, timeout=30) as client:
        client.ehlo()
        if profile.use_tls:
            client.starttls()
            client.ehlo()
        if profile.smtp_username and profile.smtp_password:
            client.login(profile.smtp_username, profile.smtp_password)
        client.send_message(message)
    return f"smtp:{profile.smtp_host}:{port}"
