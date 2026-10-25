"""Runtime configuration, read from the environment (prefix DEPARTUREBOARD_)."""

import re
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# A bare hostname: labels of letters, digits and dashes, joined by dots. No scheme, port or path.
_HOSTNAME = re.compile(r"^(?!-)[a-z0-9-]{1,63}(?<!-)(\.(?!-)[a-z0-9-]{1,63}(?<!-))*$")


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
    # HTTPS is off. "self-signed" makes a certificate on first boot under <data_dir>/tls/ and
    # serves https:// on the same port, so a TV browser can take the native wake lock. Browsers
    # warn once; see docs/tv-setup.md.
    tls: Literal["", "self-signed"] = ""
    # Or your own certificate and key (PEM paths readable by the server's user). Both or neither.
    tls_cert: Path | None = None
    tls_key: Path | None = None
    # Extra names and addresses the self-signed certificate is valid for, comma-separated:
    # "board.local,192.168.1.20". The address the TV types belongs here.
    tls_hosts: str = ""
    # A name for the board, e.g. "dboard.localhost" (Chrome and Edge resolve *.localhost to this
    # machine with no setup) or "board.local" (a LAN name your router or Bonjour resolves). Shown
    # on the settings page, pre-filled on the integrate page, added to the self-signed
    # certificate. The app does not make the name resolve; see docs/tv-setup.md.
    host: str = ""
    # How often the calendar's switch runs (seconds; 0 turns the background tick off — the
    # API's POST /api/calendar/apply still works).
    calendar_tick_seconds: float = 30

    @field_validator("host")
    @classmethod
    def _bare_hostname(cls, value: str) -> str:
        value = value.strip().lower()
        if value and not _HOSTNAME.match(value):
            raise ValueError(
                "DEPARTUREBOARD_HOST is a bare name such as dboard.localhost or board.local: "
                "no http://, no port, no path"
            )
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def tls_host_list(self) -> list[str]:
        return [h.strip() for h in self.tls_hosts.split(",") if h.strip()]

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.data_dir / 'departureboard.db'}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
