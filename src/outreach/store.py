"""SQLite-backed storage for local outreach workflow state."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .models import AuditEvent, CampaignItem, CampaignRecord, ExportOnlyResult, SuppressionEntry


def stable_lead_id(lead) -> str:
    """Compute a stable identifier for a lead for outreach state tracking."""
    place_id = getattr(lead, "place_id", None)
    if place_id:
        return f"place:{place_id}"
    company = (getattr(lead, "company_name", "") or "").strip().lower()
    city = (getattr(lead, "city", "") or "").strip().lower()
    website = (getattr(lead, "website_url", "") or "").strip().lower()
    return f"lead:{company}|{city}|{website}"


class OutreachStore:
    """Durable local store for campaigns, suppressions, and audit history."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.bootstrap()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def bootstrap(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS campaigns (
                    campaign_id TEXT PRIMARY KEY,
                    execution_mode TEXT NOT NULL,
                    sender_profile TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    title TEXT NOT NULL DEFAULT '',
                    notes TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS campaign_items (
                    item_id TEXT PRIMARY KEY,
                    campaign_id TEXT NOT NULL,
                    lead_id TEXT NOT NULL,
                    company_name TEXT NOT NULL,
                    email TEXT NOT NULL,
                    city TEXT NOT NULL,
                    country TEXT NOT NULL,
                    offer_type TEXT NOT NULL,
                    rendered_subject TEXT NOT NULL,
                    rendered_opening TEXT NOT NULL,
                    rendered_cta TEXT NOT NULL,
                    rendered_body_preview TEXT NOT NULL,
                    evidence_snapshot_json TEXT NOT NULL,
                    state TEXT NOT NULL,
                    approved_by TEXT,
                    approved_at TEXT,
                    sent_at TEXT,
                    failure_reason TEXT,
                    result_note TEXT,
                    FOREIGN KEY (campaign_id) REFERENCES campaigns(campaign_id)
                );

                CREATE TABLE IF NOT EXISTS suppressions (
                    channel TEXT NOT NULL,
                    contact_value TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    source TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    lead_id TEXT,
                    PRIMARY KEY (channel, contact_value)
                );

                CREATE TABLE IF NOT EXISTS audit_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL DEFAULT '{}'
                );
                """
            )

    def create_campaign(self, campaign: CampaignRecord) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO campaigns (
                    campaign_id, execution_mode, sender_profile, created_by, created_at, title, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    campaign.campaign_id,
                    campaign.execution_mode,
                    campaign.sender_profile,
                    campaign.created_by,
                    campaign.created_at,
                    campaign.title,
                    campaign.notes,
                ),
            )

    def get_campaign(self, campaign_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM campaigns WHERE campaign_id = ?",
                (campaign_id,),
            ).fetchone()
        return dict(row) if row is not None else None

    def list_campaigns(self) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM campaigns ORDER BY created_at DESC, campaign_id DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    def add_campaign_item(self, item: CampaignItem) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO campaign_items (
                    item_id, campaign_id, lead_id, company_name, email, city, country, offer_type,
                    rendered_subject, rendered_opening, rendered_cta, rendered_body_preview,
                    evidence_snapshot_json, state, approved_by, approved_at, sent_at,
                    failure_reason, result_note
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.item_id,
                    item.campaign_id,
                    item.lead_id,
                    item.company_name,
                    item.email,
                    item.city,
                    item.country,
                    item.offer_type,
                    item.rendered_subject,
                    item.rendered_opening,
                    item.rendered_cta,
                    item.rendered_body_preview,
                    json.dumps(item.evidence_snapshot or {}, ensure_ascii=True),
                    item.state,
                    item.approved_by,
                    item.approved_at,
                    item.sent_at,
                    item.failure_reason,
                    item.result_note,
                ),
            )

    def get_campaign_item(self, item_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM campaign_items WHERE item_id = ?",
                (item_id,),
            ).fetchone()
        if row is None:
            return None
        item = dict(row)
        item["evidence_snapshot"] = json.loads(item.pop("evidence_snapshot_json") or "{}")
        return item

    def update_campaign_item_render(
        self,
        item_id: str,
        *,
        offer_type: Optional[str] = None,
        rendered_subject: Optional[str] = None,
        rendered_opening: Optional[str] = None,
        rendered_cta: Optional[str] = None,
        rendered_body_preview: Optional[str] = None,
        evidence_snapshot: Optional[Dict[str, Any]] = None,
    ) -> None:
        current = self.get_campaign_item(item_id)
        if current is None:
            return
        payload = json.dumps(
            evidence_snapshot if evidence_snapshot is not None else current.get("evidence_snapshot", {}),
            ensure_ascii=True,
        )
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE campaign_items
                   SET offer_type = COALESCE(?, offer_type),
                       rendered_subject = COALESCE(?, rendered_subject),
                       rendered_opening = COALESCE(?, rendered_opening),
                       rendered_cta = COALESCE(?, rendered_cta),
                       rendered_body_preview = COALESCE(?, rendered_body_preview),
                       evidence_snapshot_json = ?
                 WHERE item_id = ?
                """,
                (
                    offer_type,
                    rendered_subject,
                    rendered_opening,
                    rendered_cta,
                    rendered_body_preview,
                    payload,
                    item_id,
                ),
            )

    def update_campaign_item_state(
        self,
        item_id: str,
        state: str,
        *,
        approved_by: Optional[str] = None,
        approved_at: Optional[str] = None,
        sent_at: Optional[str] = None,
        failure_reason: Optional[str] = None,
        result_note: Optional[str] = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE campaign_items
                   SET state = ?,
                       approved_by = COALESCE(?, approved_by),
                       approved_at = COALESCE(?, approved_at),
                       sent_at = COALESCE(?, sent_at),
                       failure_reason = COALESCE(?, failure_reason),
                       result_note = COALESCE(?, result_note)
                 WHERE item_id = ?
                """,
                (state, approved_by, approved_at, sent_at, failure_reason, result_note, item_id),
            )

    def list_campaign_items(
        self,
        campaign_id: str,
        *,
        states: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        query = "SELECT * FROM campaign_items WHERE campaign_id = ?"
        params: List[Any] = [campaign_id]
        if states:
            placeholders = ",".join("?" for _ in states)
            query += f" AND state IN ({placeholders})"
            params.extend(states)
        query += " ORDER BY item_id"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        result: List[Dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["evidence_snapshot"] = json.loads(item.pop("evidence_snapshot_json") or "{}")
            result.append(item)
        return result

    def add_suppression(self, entry: SuppressionEntry) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO suppressions (
                    channel, contact_value, reason, source, created_at, lead_id
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.channel,
                    entry.contact_value,
                    entry.reason,
                    entry.source,
                    entry.created_at,
                    entry.lead_id,
                ),
            )

    def is_suppressed(self, channel: str, contact_value: Optional[str]) -> bool:
        if not contact_value:
            return False
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM suppressions WHERE channel = ? AND contact_value = ?",
                (channel, contact_value),
            ).fetchone()
        return row is not None

    def list_suppressions(self) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM suppressions ORDER BY created_at DESC, channel ASC, contact_value ASC"
            ).fetchall()
        return [dict(row) for row in rows]

    def record_audit(self, event: AuditEvent) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO audit_events (
                    event_type, actor, entity_type, entity_id, created_at, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_type,
                    event.actor,
                    event.entity_type,
                    event.entity_id,
                    event.created_at,
                    json.dumps(event.payload or {}, ensure_ascii=True),
                ),
            )

    def list_audit_events(
        self,
        *,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        query = "SELECT * FROM audit_events"
        params: List[str] = []
        clauses: List[str] = []
        if entity_type:
            clauses.append("entity_type = ?")
            params.append(entity_type)
        if entity_id:
            clauses.append("entity_id = ?")
            params.append(entity_id)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY created_at DESC, event_id DESC"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        result: List[Dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["payload"] = json.loads(item.pop("payload_json") or "{}")
            result.append(item)
        return result

    def export_campaign(
        self,
        campaign_id: str,
        output_dir: str | Path,
        *,
        states: Optional[List[str]] = None,
    ) -> ExportOnlyResult:
        output_root = Path(output_dir)
        output_root.mkdir(parents=True, exist_ok=True)
        items = self.list_campaign_items(campaign_id, states=states)
        json_path = output_root / f"{campaign_id}.json"
        csv_path = output_root / f"{campaign_id}.csv"
        json_path.write_text(json.dumps(items, indent=2, ensure_ascii=True), encoding="utf-8")
        if items:
            columns = [
                "item_id",
                "lead_id",
                "company_name",
                "email",
                "city",
                "country",
                "offer_type",
                "rendered_subject",
                "rendered_opening",
                "rendered_cta",
                "rendered_body_preview",
                "state",
            ]
            lines = [",".join(columns)]
            for item in items:
                row = []
                for col in columns:
                    value = str(item.get(col, "") or "").replace('"', '""')
                    row.append(f'"{value}"')
                lines.append(",".join(row))
            csv_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        else:
            csv_path.write_text("", encoding="utf-8")
        return ExportOnlyResult(
            campaign_id=campaign_id,
            csv_path=str(csv_path),
            json_path=str(json_path),
            item_count=len(items),
        )
