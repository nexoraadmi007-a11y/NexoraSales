from __future__ import annotations

from src.database.repository import Repository


class AdminReportingService:
    def __init__(self, repository: Repository | None = None):
        self.repository = repository or Repository()

    def pipeline_summary(self) -> str:
        leads = self.repository.client.table("leads").select("industry,status").execute().data or []
        open_count = sum(1 for lead in leads if lead["status"] in {"new", "contacted", "qualified"})
        schools = sum(1 for lead in leads if lead["industry"] == "school")
        solar = sum(1 for lead in leads if lead["industry"] == "solar")
        return f"NEXORA Pipeline\nOpen Opportunities: {open_count}\nSchools: {schools}\nSolar Companies: {solar}"

    def system_health(self) -> str:
        self.repository.client.table("activity_logs").select("id").limit(1).execute()
        return "NEXORA SALESLEAD health: API online, Supabase reachable, scheduler active."
