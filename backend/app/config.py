from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "RecoverAI"
    debug: bool = True

    # SQLite keeps the local demo self-contained.
    database_url: str = "sqlite+aiosqlite:///./recoverai.db"

    # JWT
    secret_key: str = "recoverai-dev-secret-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24

    # ML
    ml_models_dir: str = "../ml/models"

    # Simulation
    live_feed_enabled: bool = False
    live_feed_interval_seconds: float = 3.0

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
