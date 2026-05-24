from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, HttpUrl


class Industry(StrEnum):
    school = "school"
    solar = "solar"


class LeadSource(StrEnum):
    google_maps = "google_maps"
    instagram = "instagram"
    linkedin = "linkedin"
    directory = "directory"
    apify = "apify"


class LeadCandidate(BaseModel):
    business_name: str
    industry: Industry
    location: str
    phone_number: str | None = None
    email: str | None = None
    website: str | None = None
    social_url: str | None = None
    contact_person: str | None = None
    estimated_organization_size: str = "Unknown"
    source: LeadSource = LeadSource.apify
    source_url: str | None = None
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class ScoredLead(LeadCandidate):
    lead_score: int
    operational_complexity_score: int
    saas_potential_score: int
    likely_operational_challenges: str
    suggested_nexora_entry_point: str
    suggested_conversation_angle: str
    notes: str = ""


class DailyLeadReport(BaseModel):
    date: datetime
    leads: list[ScoredLead]
    file_path: str | None = None

    @property
    def school_count(self) -> int:
        return sum(1 for lead in self.leads if lead.industry == Industry.school)

    @property
    def solar_count(self) -> int:
        return sum(1 for lead in self.leads if lead.industry == Industry.solar)
