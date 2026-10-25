"""Request and response shapes for the API."""

import re
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models import BUILTIN_BACKGROUNDS, THEMES, TIMER_RINGS

Repeat = Literal["none", "daily", "weekly"]
TimerRing = Literal["off", "own", "all"]
BackgroundFit = Literal["cover", "contain"]
_BG_IMAGE = re.compile(r"^(img:[a-z0-9][a-z0-9-]{0,39}|builtin:[a-z0-9][a-z0-9-]{0,39})$")
_GUEST_TOKEN = re.compile(r"^[A-Za-z0-9_-]{20,64}$")
State = Literal["live", "scheduled", "expired", "disabled"]
PostStatus = Literal["pending", "approved", "rejected"]
PostFilter = Literal["pending", "approved", "rejected", "all"]
Cell = str | dict[str, Any]  # see app.services.text

_HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class MessageIn(BaseModel):
    """A message and, optionally, when it shows.

    `starts_at` / `ends_at` bound the window (ISO-8601 with offset; either may be null).
    `repeat` narrows it to a time of day (`daily`) or to weekdays in `repeat_days` (`weekly`,
    Mon=1 … Sun=64, summed). A repeat window whose end is before its start crosses midnight.
    `show_seconds` is how long this message holds the board when it rotates with equals
    (5–600); null means the display setting `rotate_seconds`.
    """

    text: str = Field(min_length=1, max_length=2000, examples=["ZRH 0715 BOARDING"])
    enabled: bool = True
    priority: int = Field(0, ge=-100, le=100)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    repeat: Repeat = "none"
    repeat_days: int = Field(0, ge=0, le=127)
    repeat_start: str | None = Field(None, examples=["07:00"])
    repeat_end: str | None = Field(None, examples=["09:30"])
    show_seconds: int | None = Field(
        None, ge=5, le=600, description="Its own time on the board, in seconds; null = the default"
    )
    created_by: str | None = Field(None, max_length=80)

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"text": "DINNER AT 7\nBRING A COAT"},
                {
                    "text": "HAPPY BIRTHDAY NICK {yellow}",
                    "starts_at": "2026-10-21T07:00:00-04:00",
                    "ends_at": "2026-10-21T23:00:00-04:00",
                    "priority": 5,
                    "show_seconds": 60,
                },
                {
                    "text": "STANDUP 09:30 {blue}",
                    "repeat": "daily",
                    "repeat_start": "09:00",
                    "repeat_end": "10:00",
                },
                {
                    "text": "BINS OUT TONIGHT",
                    "repeat": "weekly",
                    "repeat_days": 4,
                    "repeat_start": "18:00",
                    "repeat_end": "23:00",
                },
            ]
        }
    )

    @field_validator("repeat_start", "repeat_end")
    @classmethod
    def _hhmm(cls, v: str | None) -> str | None:
        if v is not None and not _HHMM.match(v):
            raise ValueError("must be HH:MM (24 h)")
        return v

    @model_validator(mode="after")
    def _consistent(self):
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        if (self.repeat_start is None) != (self.repeat_end is None):
            raise ValueError("repeat_start and repeat_end go together")
        if self.repeat == "weekly" and self.repeat_days == 0:
            raise ValueError("a weekly repeat needs repeat_days (Mon=1 … Sun=64)")
        return self


class MessagePatch(BaseModel):
    text: str | None = Field(None, min_length=1, max_length=2000)
    enabled: bool | None = None
    priority: int | None = Field(None, ge=-100, le=100)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    repeat: Repeat | None = None
    repeat_days: int | None = Field(None, ge=0, le=127)
    repeat_start: str | None = None
    repeat_end: str | None = None
    show_seconds: int | None = Field(None, ge=5, le=600)

    _hhmm = field_validator("repeat_start", "repeat_end")(MessageIn._hhmm.__func__)


class NowIn(BaseModel):
    """The one-liner: text only, live immediately, above everything else."""

    text: str = Field(min_length=1, max_length=2000, examples=["DINNER IS READY"])
    created_by: str | None = Field(None, max_length=80)
    show_seconds: int | None = Field(None, ge=5, le=600)


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    text: str
    enabled: bool
    priority: int
    starts_at: datetime | None
    ends_at: datetime | None
    repeat: Repeat
    repeat_days: int
    repeat_start: str | None
    repeat_end: str | None
    show_seconds: int | None
    source: str
    post_id: int | None = Field(None, description="The guest post this message was made from")
    created_by: str | None
    created_at: datetime
    updated_at: datetime
    state: State
    rows: list[list[Cell]]
    used: int
    capacity: int
    unknown: list[str] = Field(default_factory=list, description="Characters shown as a blank")


class PreviewIn(BaseModel):
    text: str = Field("", max_length=2000)


class PreviewOut(BaseModel):
    """How a text lays out on the current board, for the organizer's live preview."""

    rows: list[list[Cell]]
    grid_rows: int
    grid_cols: int
    used: int
    capacity: int
    overflow: bool
    unknown: list[str]
    missing_images: list[str]


class SettingsOut(BaseModel):
    grid_preset: Literal["compact", "large", "custom"]
    rows: int
    cols: int
    animation: int
    sound_enabled: bool
    sound_volume: float
    theme: str
    poll_seconds: int
    rotate_seconds: int
    idle_text: str
    timer_ring: TimerRing
    background_image: str
    background_blur: int
    background_dim: int
    background_fit: BackgroundFit
    cell_radius: int
    cell_gap: int
    split_line: int
    guest_token: str = Field(description='The guest link\'s token; "" when guests are off')
    guest_auto_approve: bool = Field(description="A guest post goes on the board at once")
    guest_priority: int = Field(description="The priority a guest post's message gets")
    guest_show_seconds: int = Field(description="Its turn on the board, in seconds")


class SettingsPatch(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"grid_preset": "large"},
                {"grid_preset": "custom", "rows": 7, "cols": 30},
                {"animation": 0, "sound_enabled": False},
                {"theme": "walnut", "idle_text": "WELCOME HOME"},
                {"background_image": "img:poster", "background_blur": 20, "background_dim": 40},
                {"cell_radius": 0, "cell_gap": 10, "split_line": 0},
            ]
        }
    )
    grid_preset: Literal["compact", "large", "custom"] | None = None
    rows: int | None = Field(None, ge=4, le=10)
    cols: int | None = Field(None, ge=16, le=36)
    animation: int | None = Field(None, ge=0, le=100)
    sound_enabled: bool | None = None
    sound_volume: float | None = Field(None, ge=0, le=1)
    theme: str | None = Field(None, description=f"One of {', '.join(THEMES)}")
    poll_seconds: int | None = Field(None, ge=2, le=60)
    rotate_seconds: int | None = Field(None, ge=5, le=600)
    idle_text: str | None = Field(None, max_length=2000)
    timer_ring: TimerRing | None = Field(
        None, description=f"The countdown ring in the board's corner: {', '.join(TIMER_RINGS)}"
    )
    background_image: str | None = Field(
        None,
        description=(
            'A picture behind the board: "" for none, "img:<slug>" for an uploaded picture, '
            '"builtin:<name>" for a shipped one'
        ),
    )
    background_blur: int | None = Field(None, ge=0, le=40, description="Blur, px")
    background_dim: int | None = Field(None, ge=0, le=90, description="Dim, %")
    background_fit: BackgroundFit | None = None
    cell_radius: int | None = Field(
        None, ge=0, le=12, description="Corner radius of a flap, % of the cell's width"
    )
    cell_gap: int | None = Field(
        None, ge=0, le=100, description="Gap between flaps, hundredths of a vmin"
    )
    split_line: int | None = Field(
        None, ge=0, le=3, description="The line across a flap's middle, px (0 hides it)"
    )
    guest_token: str | None = Field(
        None,
        description=(
            '"" closes the guest link; POST /api/guest/rotate mints a new one. Or bring your own: '
            "20–64 letters, digits, dashes or underscores."
        ),
    )

    guest_auto_approve: bool | None = Field(
        None, description="A guest post becomes a message at once instead of waiting for you"
    )
    guest_priority: int | None = Field(
        None, ge=-100, le=100, description="The priority a guest post's message gets (default 1)"
    )
    guest_show_seconds: int | None = Field(
        None, ge=5, le=600, description="A guest post's turn on the board, seconds (default 15)"
    )

    @field_validator("guest_token")
    @classmethod
    def _guest_token(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return v
        v = v.strip()
        if not _GUEST_TOKEN.match(v):
            raise ValueError('guest_token: 20–64 letters, digits, dashes or underscores, or ""')
        return v

    @field_validator("background_image")
    @classmethod
    def _background(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return v
        v = v.strip()
        if not _BG_IMAGE.match(v):
            raise ValueError('background_image must be "", "img:<slug>" or "builtin:<name>"')
        if v.startswith("builtin:") and v[8:] not in BUILTIN_BACKGROUNDS:
            known = ", ".join(BUILTIN_BACKGROUNDS) or "none shipped yet"
            raise ValueError(f"no built-in background {v[8:]!r} ({known})")
        return v

    @field_validator("theme")
    @classmethod
    def _built_in(cls, v: str | None) -> str | None:
        if v is not None and v not in THEMES:
            raise ValueError(f"theme must be one of {', '.join(THEMES)}")
        return v


class BoardSettings(BaseModel):
    rows: int
    cols: int
    animation: int
    sound_enabled: bool
    sound_volume: float
    theme: str
    poll_seconds: int
    timer_ring: TimerRing
    background_image: str
    background_blur: int
    background_dim: int
    background_fit: BackgroundFit
    cell_radius: int
    cell_gap: int
    split_line: int


class GuestLink(BaseModel):
    """The guest link after a rotate: the token and the full address to put in a QR code."""

    token: str
    url: str


class PostOut(BaseModel):
    """A guest post in the queue and, once approved, the message it became."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    nick: str
    text: str
    image: str | None = Field(description="The photo's slug (`GET /images/{slug}`), or null")
    status: PostStatus
    message_id: int | None = Field(None, description="The message this post became, if approved")
    message_state: State | None = Field(
        None, description="That message's state; disabled when the post did not fit the board"
    )
    note: str | None = Field(
        None, description="On approve: why the message was left disabled (it does not fit)"
    )


class PostsCleared(BaseModel):
    removed: int = Field(description="Posts removed, with their messages and photos")


class BoardTimer(BaseModel):
    """The current slot while messages rotate; absent when one message has the board."""

    seconds: int = Field(description="Length of the current slot")
    remaining: int = Field(description="Seconds until the next message, at the time of the poll")
    own: bool = Field(description="The message set its own show_seconds")


class BoardCurrent(BaseModel):
    """What the board shows now. Public; polled by every TV."""

    stamp: str = Field(description="Changes whenever rows or settings change; also the ETag")
    message_id: int | None
    rows: list[list[Cell]] = Field(
        description="rows × cols cells: a character, {chip}, {img}, or {emoji}"
    )
    settings: BoardSettings
    timer: BoardTimer | None = Field(
        None,
        description="The rotation slot; left out of the stamp, so it alone never moves the ETag",
    )


Fit = Literal["contain", "cover", "stretch"]


class QrInfo(BaseModel):
    data: str


class ImageOut(BaseModel):
    slug: str
    url: str
    token: str
    content_type: str
    bytes: int
    w: int = Field(description="Cells wide on the board")
    h: int = Field(description="Cells tall on the board")
    fit: Fit = Field(description="contain keeps the shape, cover fills and crops, stretch fills")
    solid: bool = Field(
        description="Drawn whole over its block — no gap or split line through it; a QR needs it"
    )
    width: int | None = Field(description="Pixels, from the file's header; null when unreadable")
    height: int | None
    suggested: list[list[int]] = Field(
        description="[w, h] blocks that keep the picture's shape, 1–3 rows tall"
    )
    qr: QrInfo | None = Field(None, description="For a QR code the server made: its text")


class ImagePatch(BaseModel):
    """How the picture sits on the board. Send only the fields to change."""

    model_config = ConfigDict(json_schema_extra={"examples": [{"w": 9, "h": 1, "fit": "contain"}]})
    w: int | None = Field(None, ge=1, le=36)
    h: int | None = Field(None, ge=1, le=10)
    fit: Fit | None = None
    solid: bool | None = Field(
        None, description="Draw the picture whole over its block instead of slicing it per flap"
    )


class QrIn(BaseModel):
    """Make a QR code picture from text or a URL; the same slug again remakes it."""

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"slug": "menu", "data": "https://example.com/menu"}]}
    )
    slug: str = Field(
        pattern=r"^[a-z0-9][a-z0-9-]{0,39}$", description="a–z, 0–9 and dashes, up to 40"
    )
    data: str = Field(min_length=1, max_length=1024, description="The text or URL the code carries")


def as_dict(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(exclude_unset=True)
