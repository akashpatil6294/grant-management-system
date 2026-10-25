from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = ''
    supabase_url: str = ''
    supabase_publishable_key: str = ''
    frontend_origin: str = 'http://localhost:5173'
    app_timezone: str = 'Asia/Calcutta'
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')


@lru_cache
def settings():
    return Settings()
