from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", ".env.local"), extra="ignore")

    telegram_bot_token: str = ""
    telegram_bot_username: str = ""
    admin_telegram_id: str = ""
    admin_channel_id: str = ""
    customer_care_telegram_id: str = ""

    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"
    openai_embedding_model: str = "text-embedding-3-small"

    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    supabase_schema: str = "nexora_saleslead"

    redis_url: str = ""

    apify_api_key: str = ""
    apify_google_maps_actor_id: str = "compass/crawler-google-places"
    apify_instagram_actor_id: str = ""
    apify_linkedin_actor_id: str = ""

    sentry_dsn: str = ""
    timezone: str = "Africa/Lagos"
    environment: str = "production"
    report_output_dir: Path = Field(default=Path("uploads/reports"))
    log_level: str = "INFO"

    daily_school_count: int = 15
    daily_solar_count: int = 15

    @property
    def lead_delivery_chat_id(self) -> str:
        return self.customer_care_telegram_id

    @property
    def is_configured(self) -> bool:
        required = [
            self.telegram_bot_token,
            self.admin_channel_id,
            self.customer_care_telegram_id,
            self.openai_api_key,
            self.supabase_url,
            self.supabase_service_role_key,
            self.apify_api_key,
        ]
        return all(bool(value) for value in required)


@lru_cache
def get_settings() -> Settings:
    return Settings()
