from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.config.settings import Settings
from src.services.daily_leads import DailyLeadDeliveryService
from src.utils.logging import get_logger

logger = get_logger(__name__)


class NexoraScheduler(AsyncIOScheduler):
    daily_service: DailyLeadDeliveryService


def build_scheduler(settings: Settings, telegram_bot) -> NexoraScheduler:
    scheduler = NexoraScheduler(timezone=settings.timezone)
    daily_service = DailyLeadDeliveryService(settings, telegram_bot)
    scheduler.daily_service = daily_service
    scheduler.add_job(
        daily_service.run_daily_delivery,
        CronTrigger(day_of_week="mon-fri", hour=9, minute=0, timezone=settings.timezone),
        id="nexora_daily_lead_delivery_0900_africa_lagos",
        name="NEXORA weekday 30-lead Excel Telegram delivery",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=1800,
    )
    logger.info("Weekday lead scheduler registered for 09:00 Africa/Lagos")
    return scheduler
