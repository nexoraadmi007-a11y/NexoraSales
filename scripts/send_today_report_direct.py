import asyncio
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config.settings import get_settings
from src.database.repository import Repository
from src.telegram.delivery import DirectTelegramDelivery


async def main() -> None:
    settings = get_settings()
    repository = Repository()
    report = repository.get_report_for_date(datetime.now())
    if not report:
        raise SystemExit("No report exists for today.")

    file_path = Path(report["file_path"])
    if not file_path.exists():
        raise SystemExit(f"Report file does not exist: {file_path}")

    summary = (
        "NEXORA DAILY LEADS REPORT\n\n"
        f"Date: {report['report_date']}\n"
        f"Total Leads: {report['total_leads']}\n"
        f"Schools: {report['school_count']}\n"
        f"Solar Companies: {report['solar_count']}\n\n"
        "Top Opportunities:\nSee attached Excel report."
    )

    delivery = DirectTelegramDelivery(settings)
    message_id = await delivery.send_report_file(str(file_path), summary)
    await delivery.notify_admin(
        "NEXORA SALESLEAD DELIVERY CONFIRMED\n\n"
        f"Date: {report['report_date']}\n"
        f"Total Leads Sent: {report['total_leads']}\n"
        f"Schools: {report['school_count']}\n"
        f"Solar Companies: {report['solar_count']}\n"
        f"Delivered To Customer Care: {settings.lead_delivery_chat_id}\n\n"
        "Excel file was sent to customer care for calling."
    )
    repository.mark_report_delivered(report["id"], message_id)
    print({"status": "delivered", "file_path": str(file_path), "leads": report["total_leads"]})


if __name__ == "__main__":
    asyncio.run(main())
