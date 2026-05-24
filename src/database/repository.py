from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from supabase import Client

from src.database.client import get_schema_client, get_supabase
from src.models.schemas import ScoredLead


def lead_fingerprint(name: str, location: str, phone: str | None, website: str | None) -> str:
    raw = "|".join([name.lower().strip(), location.lower().strip(), phone or "", website or ""])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class Repository:
    def __init__(self, client: Client | None = None):
        self.client = get_schema_client(client or get_supabase())

    def existing_fingerprints(self, fingerprints: list[str]) -> set[str]:
        if not fingerprints:
            return set()
        res = self.client.table("leads").select("fingerprint").in_("fingerprint", fingerprints).execute()
        return {row["fingerprint"] for row in res.data or []}

    def save_leads(self, leads: list[ScoredLead]) -> list[dict[str, Any]]:
        rows = []
        for lead in leads:
            rows.append(
                {
                    "fingerprint": lead_fingerprint(lead.business_name, lead.location, lead.phone_number, lead.website),
                    "business_name": lead.business_name,
                    "industry": lead.industry.value,
                    "location": lead.location,
                    "phone_number": lead.phone_number,
                    "email": lead.email,
                    "website": lead.website,
                    "social_url": lead.social_url,
                    "contact_person": lead.contact_person,
                    "estimated_organization_size": lead.estimated_organization_size,
                    "source": lead.source.value,
                    "source_url": lead.source_url,
                    "raw_payload": lead.raw_payload,
                    "status": "new",
                    "created_by": "system",
                    "updated_by": "system",
                }
            )
        res = self.client.table("leads").upsert(rows, on_conflict="fingerprint").execute()
        saved = res.data or []
        score_rows = []
        for row, lead in zip(saved, leads, strict=False):
            score_rows.append(
                {
                    "lead_id": row["id"],
                    "lead_score": lead.lead_score,
                    "operational_complexity_score": lead.operational_complexity_score,
                    "saas_potential_score": lead.saas_potential_score,
                    "likely_operational_challenges": lead.likely_operational_challenges,
                    "suggested_nexora_entry_point": lead.suggested_nexora_entry_point,
                    "suggested_conversation_angle": lead.suggested_conversation_angle,
                    "notes": lead.notes,
                    "created_by": "system",
                    "updated_by": "system",
                }
            )
        if score_rows:
            self.client.table("lead_scores").insert(score_rows).execute()
        return saved

    def create_report(self, report_date: datetime, file_path: str, total: int, schools: int, solar: int) -> dict[str, Any]:
        res = self.client.table("reports").insert(
            {
                "report_type": "daily_leads",
                "report_date": report_date.date().isoformat(),
                "file_path": file_path,
                "total_leads": total,
                "school_count": schools,
                "solar_count": solar,
                "delivery_status": "generated",
                "created_by": "system",
                "updated_by": "system",
            }
        ).execute()
        return (res.data or [{}])[0]

    def update_report_generated(self, report_id: str, file_path: str, total: int, schools: int, solar: int) -> dict[str, Any]:
        res = self.client.table("reports").update(
            {
                "file_path": file_path,
                "total_leads": total,
                "school_count": schools,
                "solar_count": solar,
                "delivery_status": "generated",
                "updated_by": "system",
            }
        ).eq("id", report_id).execute()
        return (res.data or [{}])[0]

    def get_report_for_date(self, report_date: datetime, report_type: str = "daily_leads") -> dict[str, Any] | None:
        res = self.client.table("reports").select("*").eq("report_type", report_type).eq("report_date", report_date.date().isoformat()).limit(1).execute()
        return (res.data or [None])[0]

    def mark_report_delivered(self, report_id: str, telegram_message_id: int | None) -> None:
        self.client.table("reports").update(
            {
                "delivery_status": "delivered",
                "telegram_message_id": telegram_message_id,
                "delivered_at": datetime.now(timezone.utc).isoformat(),
                "updated_by": "system",
            }
        ).eq("id", report_id).execute()

    def log_activity(self, activity_type: str, message: str, metadata: dict[str, Any] | None = None) -> None:
        self.client.table("activity_logs").insert(
            {
                "activity_type": activity_type,
                "message": message,
                "metadata": metadata or {},
                "created_by": "system",
            }
        ).execute()
