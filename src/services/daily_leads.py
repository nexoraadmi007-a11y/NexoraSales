from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import redis.asyncio as redis
from redis.exceptions import RedisError

from src.config.settings import Settings
from src.database.repository import Repository
from src.lead_generation.scoring import LeadScorer
from src.lead_generation.scraper import ApifyLeadScraper
from src.models.schemas import DailyLeadReport, Industry
from src.reports.excel import ExcelReportBuilder
from src.utils.logging import get_logger

logger = get_logger(__name__)


class DailyLeadDeliveryService:
    def __init__(self, settings: Settings, telegram_bot, repository: Repository | None = None):
        self.settings = settings
        self.telegram_bot = telegram_bot
        self.repository = repository or Repository()
        self.scraper = ApifyLeadScraper(settings, self.repository)
        self.scorer = LeadScorer()
        self.excel = ExcelReportBuilder(settings.report_output_dir)

    async def run_daily_delivery(self) -> dict:
        now = datetime.now(ZoneInfo(self.settings.timezone))
        existing = self.repository.get_report_for_date(now)
        if existing and existing.get("delivery_status") == "delivered":
            return {"status": "skipped", "reason": "daily report already delivered", "report_id": existing["id"]}
        if existing and existing.get("delivery_status") == "generated" and existing.get("file_path") and Path(existing["file_path"]).exists():
            message_id = await self._send_existing_with_retry(existing)
            await self.telegram_bot.notify_admin(self._admin_delivery_summary(existing))
            self.repository.mark_report_delivered(existing["id"], message_id)
            return {"status": "delivered", "leads": existing["total_leads"], "file_path": existing["file_path"], "resend": True}

        lock_key = f"nexora:saleslead:daily-report:{now.date().isoformat()}"
        redis_client = redis.from_url(self.settings.redis_url, decode_responses=True) if self.settings.redis_url else None
        redis_available = True
        try:
            locked = await redis_client.set(lock_key, "running", nx=True, ex=3600) if redis_client else True
        except RedisError as exc:
            redis_available = False
            locked = True
            logger.warning("Redis lock unavailable; continuing with database duplicate protection", extra={"error": str(exc)})
        if not locked:
            if redis_client:
                await redis_client.aclose()
            return {"status": "skipped", "reason": "daily report job already running"}

        logger.info("Daily lead delivery started")
        try:
            schools = await self.scraper.collect(Industry.school, self.settings.daily_school_count)
            solar = await self.scraper.collect(Industry.solar, self.settings.daily_solar_count)
            scored = [self.scorer.score(lead) for lead in [*schools, *solar]]
            if len(scored) < self.settings.daily_school_count + self.settings.daily_solar_count:
                self.repository.log_activity("lead_generation_underfilled", "Daily lead target underfilled", {"count": len(scored)})

            report = DailyLeadReport(date=now, leads=scored)
            file_path = self.excel.build(report)
            saved = self.repository.save_leads(scored)
            db_report = (
                self.repository.update_report_generated(existing["id"], file_path, len(scored), report.school_count, report.solar_count)
                if existing
                else self.repository.create_report(now, file_path, len(scored), report.school_count, report.solar_count)
            )
            message_id = await self._send_with_retry(file_path, report)
            self.repository.mark_report_delivered(db_report["id"], message_id)
            self.repository.log_activity("daily_report_delivered", "Daily lead report delivered to Telegram", {"report_id": db_report["id"], "leads": len(saved)})
            return {"status": "delivered", "leads": len(scored), "file_path": file_path}
        except Exception as exc:
            self.repository.log_activity("daily_report_failed", "Daily lead report failed", {"error": str(exc)})
            raise
        finally:
            if redis_available and redis_client:
                await redis_client.delete(lock_key)
            if redis_client:
                await redis_client.aclose()

    async def _send_with_retry(self, file_path: str, report: DailyLeadReport) -> int | None:
        last_error: Exception | None = None
        for attempt in range(1, 4):
            try:
                return await self.telegram_bot.send_daily_report(file_path, report)
            except Exception as exc:
                last_error = exc
                self.repository.log_activity("telegram_delivery_retry", "Retrying Telegram report delivery", {"attempt": attempt, "error": str(exc)})
        if self.settings.admin_telegram_id:
            await self.telegram_bot.notify_admin(f"NEXORA daily report delivery failed after retries: {last_error}")
        raise RuntimeError(f"Telegram delivery failed after retries: {last_error}")

    async def _send_existing_with_retry(self, db_report: dict) -> int | None:
        summary = (
            "NEXORA DAILY LEADS REPORT\n\n"
            f"Date: {db_report['report_date']}\n"
            f"Total Leads: {db_report['total_leads']}\n"
            f"Schools: {db_report['school_count']}\n"
            f"Solar Companies: {db_report['solar_count']}\n\n"
            "Top Opportunities:\nSee attached Excel report."
        )
        last_error: Exception | None = None
        for attempt in range(1, 4):
            try:
                return await self.telegram_bot.send_report_file(db_report["file_path"], summary)
            except Exception as exc:
                last_error = exc
                self.repository.log_activity("telegram_delivery_retry", "Retrying existing Telegram report delivery", {"attempt": attempt, "error": str(exc)})
        if self.settings.admin_telegram_id:
            await self.telegram_bot.notify_admin(f"NEXORA existing report delivery failed after retries: {last_error}")
        raise RuntimeError(f"Telegram existing report delivery failed after retries: {last_error}")

    def summary_message(self, report: DailyLeadReport) -> str:
        top = sorted(report.leads, key=lambda lead: lead.lead_score, reverse=True)[:3]
        top_lines = "\n".join(f"- {lead.business_name} ({lead.industry.value}, score {lead.lead_score})" for lead in top)
        return (
            "NEXORA DAILY LEADS REPORT\n\n"
            f"Date: {report.date.strftime('%Y-%m-%d')}\n"
            f"Total Leads: {len(report.leads)}\n"
            f"Schools: {report.school_count}\n"
            f"Solar Companies: {report.solar_count}\n\n"
            f"Top Opportunities:\n{top_lines}"
        )

    def _admin_delivery_summary(self, db_report: dict) -> str:
        return (
            "NEXORA SALESLEAD DELIVERY CONFIRMED\n\n"
            f"Date: {db_report['report_date']}\n"
            f"Total Leads Sent: {db_report['total_leads']}\n"
            f"Schools: {db_report['school_count']}\n"
            f"Solar Companies: {db_report['solar_count']}\n"
            f"Delivered To Customer Care: {self.settings.lead_delivery_chat_id}\n\n"
            "Excel file was sent to customer care for calling."
        )
