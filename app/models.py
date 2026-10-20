"""The two tables: messages on the board, and display settings."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Window (UTC). Either side may be open.
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # none | daily | weekly
    repeat: Mapped[str] = mapped_column(String(8), nullable=False, default="none")
    # Weekly bitmask: Mon=1 … Sun=64
    repeat_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Time of day in the configured timezone, "HH:MM"
    repeat_start: Mapped[str | None] = mapped_column(String(5))
    repeat_end: Mapped[str | None] = mapped_column(String(5))
    # ui | api | agent
    source: Mapped[str] = mapped_column(String(8), nullable=False, default="api")
    created_by: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(40), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)


# Display presets: rows × columns. Compact is the classic 6×22 grid for a 42–48" TV,
# Large adds rows and columns for a 55–77" TV. Custom stays within the bounds.
PRESETS = {"compact": (6, 22), "large": (8, 28)}
ROWS_BOUNDS = (4, 10)
COLS_BOUNDS = (16, 36)

DEFAULT_SETTINGS = {
    "grid_preset": "compact",
    "rows": "6",
    "cols": "22",
    "animation": "60",
    "sound_enabled": "true",
    "sound_volume": "0.6",
    "theme": "classic-black",
    "poll_seconds": "5",
    "rotate_seconds": "20",
    "idle_text": "",
}
