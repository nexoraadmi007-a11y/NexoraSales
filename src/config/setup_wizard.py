from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import redis.asyncio as redis
from openai import AsyncOpenAI
from supabase import create_client

REQUIRED_KEYS = [
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_BOT_USERNAME",
    "ADMIN_TELEGRAM_ID",
    "ADMIN_CHANNEL_ID",
    "CUSTOMER_CARE_TELEGRAM_ID",
    "OPENAI_API_KEY",
    "APIFY_API_KEY",
    "SUPABASE_URL",
    "SUPABASE_ANON_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
    "SUPABASE_SCHEMA",
    "REDIS_URL",
]


class SetupWizard:
    def __init__(self, env_path: Path = Path(".env")):
        self.env_path = env_path

    async def validate(self, config: dict[str, str]) -> list[str]:
        errors: list[str] = []
        missing = [key for key in REQUIRED_KEYS if not config.get(key)]
        errors.extend(f"Missing {key}" for key in missing)
        duplicate_values = self._duplicates(config)
        errors.extend(f"Duplicate config value detected for {','.join(keys)}" for keys in duplicate_values)
        if errors:
            return errors

        async with httpx.AsyncClient(timeout=15) as client:
            telegram = await client.get(f"https://api.telegram.org/bot{config['TELEGRAM_BOT_TOKEN']}/getMe")
            if telegram.status_code != 200 or not telegram.json().get("ok"):
                errors.append("Invalid TELEGRAM_BOT_TOKEN")

            apify = await client.get(
                "https://api.apify.com/v2/users/me",
                headers={"Authorization": f"Bearer {config['APIFY_API_KEY']}"},
            )
            if apify.status_code != 200:
                errors.append("Invalid APIFY_API_KEY")

        try:
            await AsyncOpenAI(api_key=config["OPENAI_API_KEY"]).models.list()
        except Exception as exc:
            errors.append(f"Invalid OPENAI_API_KEY: {exc}")

        try:
            create_client(config["SUPABASE_URL"], config["SUPABASE_SERVICE_ROLE_KEY"]).schema(config["SUPABASE_SCHEMA"]).table("users").select("id").limit(1).execute()
        except Exception as exc:
            errors.append(f"Supabase validation failed. Run schema migration first if tables do not exist: {exc}")

        try:
            r = redis.from_url(config["REDIS_URL"], decode_responses=True)
            await r.ping()
            await r.aclose()
        except Exception as exc:
            errors.append(f"Invalid REDIS_URL: {exc}")

        return errors

    def write_env(self, config: dict[str, str]) -> None:
        lines = [f"{key}={config.get(key, '')}" for key in REQUIRED_KEYS]
        self.env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    @staticmethod
    def _duplicates(config: dict[str, str]) -> list[list[str]]:
        seen: dict[str, list[str]] = {}
        for key, value in config.items():
            if value and key.endswith(("KEY", "TOKEN", "URL")):
                seen.setdefault(value, []).append(key)
        return [keys for keys in seen.values() if len(keys) > 1]


async def main() -> None:
    wizard = SetupWizard()
    config = {key: input(f"{key}= ").strip() for key in REQUIRED_KEYS}
    errors = await wizard.validate(config)
    if errors:
        raise SystemExit("\n".join(errors))
    wizard.write_env(config)
    print("NEXORA SALESLEAD setup complete.")


if __name__ == "__main__":
    asyncio.run(main())
