"""Runtime configuration, read from the environment (prefix DEPARTUREBOARD_)."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DEPARTUREBOARD_", env_file=".env", extra="ignore")

    # Where the SQLite database and the generated API token live.
    data_dir: Path = Path("./data")
    # Set this to use your own token; leave blank to generate one on first boot.
    api_token: str | None = None
    # Timezone schedules are evaluated in (IANA name). The TZ env var is also honoured.
    tz: str = "UTC"
    # CORS is off. To let a browser app on another origin call the API, list the origins,
    # comma-separated: "https://dash.example.com,http://localhost:5173".
    cors_origins: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.data_dir / 'departureboard.db'}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
