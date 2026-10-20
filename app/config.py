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

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.data_dir / 'departureboard.db'}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
