from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.database.repository import Repository


class FollowUpEngine:
    windows = [
        (timedelta(hours=24), "soft_follow_up", "Check in naturally and reopen the conversation."),
        (timedelta(hours=48), "value_follow_up", "Send a useful operational insight tied to their business."),
        (timedelta(hours=72), "operational_reminder", "Remind them of the workflow gap or missed opportunity."),
        (timedelta(days=5), "close_loop", "Close the loop politely while leaving a clear next step."),
    ]

    def __init__(self, repository: Repository | None = None):
        self.repository = repository or Repository()

    def due_followups(self) -> list[dict]:
        now = datetime.now(timezone.utc)
        res = self.repository.client.table("followups").select("*").lte("next_followup_at", now.isoformat()).eq("status", "pending").execute()
        return res.data or []

    def schedule_next(self, conversation_id: str, last_interaction_at: datetime) -> None:
        for delta, kind, guidance in self.windows:
            self.repository.client.table("followups").insert(
                {
                    "conversation_id": conversation_id,
                    "followup_type": kind,
                    "next_followup_at": (last_interaction_at + delta).isoformat(),
                    "status": "pending",
                    "guidance": guidance,
                    "created_by": "system",
                    "updated_by": "system",
                }
            ).execute()
