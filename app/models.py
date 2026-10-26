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
    # Seconds this message holds the board when rotating with equals; None = rotate_seconds
    show_seconds: Mapped[int | None] = mapped_column(Integer)
    # ui | api | agent | guest
    source: Mapped[str] = mapped_column(String(8), nullable=False, default="api")
    # The guest post this message was made from (source guest); clearing the post removes it
    post_id: Mapped[int | None] = mapped_column(Integer)
    created_by: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class Post(Base):
    """What a guest left through the guest link: a line, a photo or both, waiting for the host."""

    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    nick: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    text: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    # the slug of the photo under <data_dir>/images (guest-<id>), or None
    image: Mapped[str | None] = mapped_column(String(40))
    # pending | approved | rejected
    status: Mapped[str] = mapped_column(String(8), nullable=False, default="pending")
    # a salted hash of the poster's address, for the hourly limit — never the address itself
    ip_hash: Mapped[str] = mapped_column(String(16), nullable=False, default="")


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(40), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)


# Display presets: rows × columns. Compact is the classic 6×22 grid for a 42–48" TV,
# Large adds rows and columns for a 55–77" TV. Custom stays within the bounds.
PRESETS = {"compact": (6, 22), "large": (8, 28)}
ROWS_BOUNDS = (4, 10)
COLS_BOUNDS = (16, 36)

# The shape of a flap: corner radius in % of the cell's width, the gap between cells in
# hundredths of a vmin, the split line across the middle in px (0 hides it).
FLAP_BOUNDS = {"cell_radius": (0, 12), "cell_gap": (0, 100), "split_line": (0, 3)}
# The depth of a flap: its shading and the shadow under it, 0–100; "" = as the theme.
CELL_DEPTH_BOUNDS = (0, 100)

# Built-in themes: app/static/themes/<id>.css. The first is the default.
THEMES = ("classic-black", "walnut", "arctic-white", "midnight", "gsx-terminal")

# The frame (the bezel around the board): width and outer corner radius in vmin when set; "" on
# any frame key means "as the theme" — the theme's stylesheet carries its native look.
# A theme's name on the settings page when title-casing its id is not it.
THEME_NAMES = {"gsx-terminal": "GSX Terminal"}

FRAME_BOUNDS = {"frame_width": (0, 10), "frame_radius": (0, 30)}
FRAME_FINISHES = ("theme", "matte", "chrome", "neon")
# Where the frame sits: filling the screen (the classic slab) or hugging the flaps so the page
# or the backdrop shows around it; the board's size as % of the screen; the board's own colour
# between the bezel and the flaps, in vmin (it also absorbs a round corner).
FRAME_FITS = ("screen", "board")
# The corner flaps: "whole" = the board's inner corner rounds only as far as the margin allows
# (the bezel thickens at the corners); "hide" = the bezel's inner curve follows its outer one and
# hides whatever of the corner flaps it covers — and the corner cap is lifted.
FRAME_CORNERS = ("whole", "hide")
BOARD_BOUNDS = {"board_scale": (25, 100), "board_margin": (0, 10)}

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
    "timer_ring": "off",
    # Behind the board: "" (none), "img:<slug>" (an uploaded picture), "builtin:<name>" (a shipped
    # one) or "video:<slug>" (an uploaded clip, muted in a loop); blurred by background_blur px,
    # dimmed by background_dim %, cover or contain.
    "background_image": "",
    "background_blur": "12",
    "background_dim": "30",
    "background_fit": "cover",
    # The shape of a flap (FLAP_BOUNDS): 6 % corners, a 0.35 vmin gap, a 1 px split line.
    "cell_radius": "6",
    "cell_gap": "35",
    "split_line": "1",
    "cell_depth": "",
    # The frame (FRAME_BOUNDS / FRAME_FINISHES): colour, width, corner radius, finish and the neon
    # glow colour; "" = as the theme, finish "theme" = the theme's own.
    "frame_color": "",
    "frame_width": "",
    "frame_radius": "",
    "frame_finish": "theme",
    "frame_glow": "",
    "frame_fit": "screen",
    "frame_corners": "whole",
    "board_scale": "100",
    "board_margin": "0",
    # The first-run walkthrough: "" shows it when the settings page opens, "1" once Done or
    # skipped. DELETE /api/settings/setup_done brings it back. Never sent to the TV.
    "setup_done": "",
    # The guest link: "" = off; a token mints with POST /api/guest/rotate. Never sent to the TV.
    "guest_token": "",
    # Guest posts wait for the host unless auto-approve is on; each becomes a message at this
    # priority (guests take turns among themselves), holding the board this many seconds.
    "guest_auto_approve": "false",
    "guest_priority": "1",
    "guest_show_seconds": "15",
    # The profile loaded last (profiles/<slug>.json), "" when none — informational; a save or a
    # load sets it. Not part of a profile, never sent to the TV.
    "active_profile": "",
    # The calendar: the saved board between planned days ("" = stay on the last one), and what
    # the switch applied last (internal; "entry:<id>:<slug>", "everyday:<slug>" or "").
    "calendar_everyday": "",
    "calendar_applied": "",
}

GUEST_BOUNDS = {"guest_priority": (-100, 100), "guest_show_seconds": (5, 600)}

POST_STATUSES = ("pending", "approved", "rejected")

# Shipped backgrounds: app/static/backgrounds/<name>.jpg, 1920×1080, drawn by the project (no
# third-party pictures), with a 320×180 thumbnail under thumbs/. Chosen as "builtin:<name>".
BUILTIN_BACKGROUNDS: tuple[str, ...] = ("terminal", "wood", "gala", "paper")

# The countdown ring in the board's corner: never, for messages with their own show_seconds, or
# for every rotating message.
TIMER_RINGS = ("off", "own", "all")
