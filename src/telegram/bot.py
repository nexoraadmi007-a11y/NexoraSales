from __future__ import annotations

from telegram import Update
from telegram.error import TelegramError, TimedOut
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from src.admin.reporting import AdminReportingService
from src.agents.assistant import ConversationAssistant
from src.config.settings import Settings
from src.models.schemas import DailyLeadReport
from src.telegram.delivery import DirectTelegramDelivery
from src.utils.logging import get_logger

logger = get_logger(__name__)


class NexoraTelegramBot:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.application: Application | None = None
        self.assistant = ConversationAssistant(settings)
        self.admin = AdminReportingService() if settings.supabase_service_role_key else None
        self.delivery = DirectTelegramDelivery(settings)

    async def start(self) -> None:
        if not self.settings.telegram_bot_token:
            logger.warning("Telegram bot token missing; bot will not start.")
            return
        self.application = Application.builder().token(self.settings.telegram_bot_token).build()
        self._register_handlers(self.application)
        try:
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling(drop_pending_updates=True)
        except (TelegramError, TimedOut) as exc:
            logger.error("Telegram bot startup failed; API will continue and direct delivery will remain available", extra={"error": str(exc)})
            self.application = None

    async def stop(self) -> None:
        if not self.application:
            return
        await self.application.updater.stop()
        await self.application.stop()
        await self.application.shutdown()

    def _register_handlers(self, app: Application) -> None:
        app.add_handler(CommandHandler("start", self.start_command))
        app.add_handler(CommandHandler("help", self.help_command))
        app.add_handler(CommandHandler("my_leads", self.my_leads_command))
        app.add_handler(CommandHandler("switch", self.switch_command))
        app.add_handler(CommandHandler("analyze", self.analyze_command))
        app.add_handler(CommandHandler("done", self.done_command))
        app.add_handler(CommandHandler("admin_report", self.admin_report_command))
        app.add_handler(CommandHandler("pipeline", self.pipeline_command))
        app.add_handler(CommandHandler("system_health", self.system_health_command))
        app.add_handler(CommandHandler("export", self.export_command))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.free_text_handler))

    async def send_daily_report(self, file_path: str, report: DailyLeadReport) -> int | None:
        return await self.delivery.send_daily_report(file_path, report)

    async def send_report_file(self, file_path: str, summary: str) -> int | None:
        return await self.delivery.send_report_file(file_path, summary)

    async def notify_admin(self, text: str) -> None:
        try:
            await self.delivery.notify_admin(text)
        except TelegramError as exc:
            logger.error("Admin notification failed", extra={"error": str(exc)})

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text("NEXORA SALESLEAD is online. Use /help for agent commands.")

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text(
            "Agent: /my_leads /switch /analyze /done\n"
            "Admin: /admin_report /pipeline /system_health /export"
        )

    async def my_leads_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text("Your assigned leads will appear here after admin assignment.")

    async def switch_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text("Agent context switched. Send the business name or chat thread next.")

    async def analyze_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        text = " ".join(context.args)
        if not text:
            await update.message.reply_text("Paste the customer chat after /analyze.")
            return
        result = await self.assistant.analyze_chat(text)
        await update.message.reply_text(result)

    async def done_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text("Conversation marked done. Follow-up tracking can continue from admin pipeline.")

    async def admin_report_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._admin_only(update, "Daily admin reporting is active. Use /pipeline for current pipeline summary.")

    async def pipeline_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        text = self.admin.pipeline_summary() if self.admin else "Supabase is not configured."
        await self._admin_only(update, text)

    async def system_health_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        text = self.admin.system_health() if self.admin else "NEXORA SALESLEAD health: bot online, database not configured."
        await self._admin_only(update, text)

    async def export_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._admin_only(update, "Weekday reports run at 9:00 AM Africa/Lagos and send Excel to customer care.")

    async def free_text_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        text = update.message.text or ""
        if len(text) < 80:
            return
        result = await self.assistant.analyze_chat(text)
        await update.message.reply_text(result)

    async def _admin_only(self, update: Update, text: str) -> None:
        user_id = str(update.effective_user.id)
        if self.settings.admin_telegram_id and user_id != self.settings.admin_telegram_id:
            await update.message.reply_text("Admin access required.")
            return
        await update.message.reply_text(text)
