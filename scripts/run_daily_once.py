import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config.settings import get_settings
from src.services.daily_leads import DailyLeadDeliveryService
from src.telegram.delivery import DirectTelegramDelivery


async def main() -> None:
    settings = get_settings()
    delivery = DirectTelegramDelivery(settings)
    result = await DailyLeadDeliveryService(settings, delivery).run_daily_delivery()
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
