from __future__ import annotations

from pathlib import Path

import httpx

from src.config.settings import Settings
from src.models.schemas import DailyLeadReport


class DirectTelegramDelivery:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.base_url = f"https://api.telegram.org/bot{settings.telegram_bot_token}"

    async def send_daily_report(self, file_path: str, report: DailyLeadReport) -> int | None:
        customer_summary = self._customer_summary(report)
        admin_summary = self._admin_summary(
            date=report.date.strftime("%Y-%m-%d"),
            total=len(report.leads),
            schools=report.school_count,
            solar=report.solar_count,
            delivered_to=self.settings.lead_delivery_chat_id,
        )
        message_id = await self.send_report_file(file_path, customer_summary)
        await self.notify_admin(admin_summary)
        return message_id

    async def send_report_file(self, file_path: str, summary: str) -> int | None:
        target_chat_id = self.settings.lead_delivery_chat_id
        if not target_chat_id:
            raise RuntimeError("CUSTOMER_CARE_TELEGRAM_ID is required for report delivery.")
        path = Path(file_path)
        async with httpx.AsyncClient(timeout=120) as client:
            message = await client.post(
                f"{self.base_url}/sendMessage",
                data={"chat_id": target_chat_id, "text": summary},
            )
            message.raise_for_status()
            with path.open("rb") as handle:
                document = await client.post(
                    f"{self.base_url}/sendDocument",
                    data={"chat_id": target_chat_id, "caption": "Professional Excel lead report attached."},
                    files={
                        "document": (
                            path.name,
                            handle,
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        )
                    },
                )
            document.raise_for_status()
            return document.json()["result"]["message_id"]

    async def notify_admin(self, text: str) -> None:
        admin_chat_id = self.settings.admin_telegram_id or self.settings.admin_channel_id
        if not admin_chat_id:
            return
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{self.base_url}/sendMessage",
                data={"chat_id": admin_chat_id, "text": text},
            )
            response.raise_for_status()

    def _customer_summary(self, report: DailyLeadReport) -> str:
        top = sorted(report.leads, key=lambda lead: lead.lead_score, reverse=True)[:5]
        top_lines = "\n".join(f"- {lead.business_name} ({lead.industry.value}, score {lead.lead_score})" for lead in top)
        return (
            "NEXORA DAILY LEADS REPORT\n\n"
            f"Date: {report.date.strftime('%Y-%m-%d')}\n"
            f"Total Leads: {len(report.leads)}\n"
            f"Schools: {report.school_count}\n"
            f"Solar Companies: {report.solar_count}\n\n"
            f"Top Opportunities:\n{top_lines}"
        )

    @staticmethod
    def _admin_summary(date: str, total: int, schools: int, solar: int, delivered_to: str) -> str:
        return (
            "NEXORA SALESLEAD DELIVERY CONFIRMED\n\n"
            f"Date: {date}\n"
            f"Total Leads Sent: {total}\n"
            f"Schools: {schools}\n"
            f"Solar Companies: {solar}\n"
            f"Delivered To Customer Care: {delivered_to}\n\n"
            "Excel file was sent to customer care for calling."
        )
