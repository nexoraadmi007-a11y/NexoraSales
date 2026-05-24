from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI
from sentry_sdk.integrations.fastapi import FastApiIntegration

from src.config.settings import get_settings
from src.cron.scheduler import build_scheduler
from src.telegram.bot import NexoraTelegramBot
from src.utils.logging import configure_logging, get_logger

settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger(__name__)

if settings.sentry_dsn:
    sentry_sdk.init(dsn=settings.sentry_dsn, integrations=[FastApiIntegration()])


@asynccontextmanager
async def lifespan(app: FastAPI):
    telegram_bot = NexoraTelegramBot(settings)
    scheduler = build_scheduler(settings, telegram_bot)
    app.state.telegram_bot = telegram_bot
    app.state.scheduler = scheduler

    await telegram_bot.start()
    scheduler.start()
    logger.info("NEXORA SALESLEAD started", extra={"timezone": settings.timezone})
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)
        await telegram_bot.stop()


app = FastAPI(
    title="NEXORA SALESLEAD",
    description="NEXORA Operational Sales & Execution Core",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    return {"status": "ok", "system": "NEXORA SALESLEAD", "timezone": settings.timezone}


@app.post("/jobs/daily-leads/run")
async def run_daily_leads_now():
    result = await app.state.scheduler.daily_service.run_daily_delivery()
    return result
