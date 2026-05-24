from functools import lru_cache

from supabase import Client, create_client

from src.config.settings import get_settings


@lru_cache
def get_supabase() -> Client:
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise RuntimeError("Supabase service configuration is missing.")
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


def get_schema_client(client: Client | None = None):
    settings = get_settings()
    base = client or get_supabase()
    return base.schema(settings.supabase_schema)
