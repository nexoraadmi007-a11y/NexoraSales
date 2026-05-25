from __future__ import annotations

from pathlib import Path

import httpx

from src.config.settings import Settings
from src.models.schemas import DailyLeadReport


class TelegramDeliveryError(RuntimeError):
    def __init__(self, method: str, chat_id: str, status_code: int, description: str):
        chat_tail = chat_id[-4:] if chat_id else "none"
        super().__init__(
            f"Telegram {method} failed for chat ending {chat_tail}: "
            f"{status_code} {description}"
        )


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
        try:
            message_id = await self.send_report_file(file_path, customer_summary)
        except TelegramDeliveryError as exc:
            await self._send_admin_fallback(file_path, report, exc)
            return None

        await self._notify_admin_best_effort(admin_summary)
        return message_id

    async def send_report_file(self, file_path: str, summary: str) -> int | None:
        target_chat_id = self.settings.lead_delivery_chat_id
        if not target_chat_id:
            raise RuntimeError("CUSTOMER_CARE_TELEGRAM_ID is required for report delivery.")
        return await self.send_report_file_to_chat(
            chat_id=target_chat_id,
            file_path=file_path,
            summary=summary,
            caption="Professional Excel lead report attached.",
        )

    async def send_report_file_to_chat(self, chat_id: str, file_path: str, summary: str, caption: str) -> int | None:
        path = Path(file_path)
        async with httpx.AsyncClient(timeout=120) as client:
            await self._post_telegram(
                client,
                "sendMessage",
                data={"chat_id": chat_id, "text": summary},
            )
            with path.open("rb") as handle:
                document = await self._post_telegram(
                    client,
                    "sendDocument",
                    data={"chat_id": chat_id, "caption": caption},
                    files={
                        "document": (
                            path.name,
                            handle,
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        )
                    },
                )
            return document.json()["result"]["message_id"]

    async def notify_admin(self, text: str) -> None:
        admin_chat_id = self._admin_chat_id()
        if not admin_chat_id:
            return
        async with httpx.AsyncClient(timeout=60) as client:
            await self._post_telegram(
                client,
                "sendMessage",
                data={"chat_id": admin_chat_id, "text": text},
            )

    async def _send_admin_fallback(self, file_path: str, report: DailyLeadReport, error: TelegramDeliveryError) -> None:
        admin_chat_id = self._admin_chat_id()
        if not admin_chat_id:
            raise error
        alert = (
            "NEXORA CUSTOMER-CARE DELIVERY FAILED\n\n"
            f"Date: {report.date.strftime('%Y-%m-%d')}\n"
            f"Total Leads Generated: {len(report.leads)}\n"
            f"Schools: {report.school_count}\n"
            f"Solar Companies: {report.solar_count}\n\n"
            f"Reason: {error}\n\n"
            "Emergency fallback: the Excel lead report is attached here for admin review.\n"
            "Ask customer care to open @NexoraSalesbot and press Start, then confirm the Telegram ID."
        )
        await self.send_report_file_to_chat(
            chat_id=admin_chat_id,
            file_path=file_path,
            summary=alert,
            caption="Fallback Excel lead report attached.",
        )

    async def _notify_admin_best_effort(self, text: str) -> None:
        try:
            await self.notify_admin(text)
        except TelegramDeliveryError:
            return

    async def _post_telegram(
        self,
        client: httpx.AsyncClient,
        method: str,
        *,
        data: dict[str, str],
        files: dict | None = None,
    ) -> httpx.Response:
        response = await client.post(f"{self.base_url}/{method}", data=data, files=files)
        if response.is_success:
            return response
        description = self._telegram_error_description(response)
        raise TelegramDeliveryError(method, str(data.get("chat_id", "")), response.status_code, description)

    @staticmethod
    def _telegram_error_description(response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return response.text[:200] or "unknown Telegram error"
        description = payload.get("description") if isinstance(payload, dict) else None
        return str(description or "unknown Telegram error")

    def _admin_chat_id(self) -> str:
        return self.settings.admin_telegram_id or self.settings.admin_channel_id

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
