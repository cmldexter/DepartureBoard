"""The display settings the board page needs, typed and bounded.

Reads the `settings` table, overlays the defaults, and resolves the grid preset into rows and
columns. Pure over a session so the board page, and later the board and settings APIs, share it.
"""

import re
from collections.abc import Mapping
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    BOARD_BOUNDS,
    CELL_DEPTH_BOUNDS,
    COLS_BOUNDS,
    DEFAULT_SETTINGS,
    FLAP_BOUNDS,
    FRAME_BOUNDS,
    FRAME_FINISHES,
    FRAME_FITS,
    GUEST_BOUNDS,
    PRESETS,
    ROWS_BOUNDS,
    TIMER_RINGS,
    Setting,
)

ANIMATION_BOUNDS = (0, 100)


def _clamp(value: int, bounds: tuple[int, int]) -> int:
    low, high = bounds
    return max(low, min(high, value))


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


_HEX = re.compile(r"^#[0-9a-f]{6}$")


def _as_color(value: Any) -> str:
    """A "#rrggbb" colour lowercased, else "" (as the theme)."""
    v = str(value or "").strip().lower()
    return v if _HEX.match(v) else ""


def _opt_int(value: Any, bounds: tuple[int, int]) -> int | str:
    """ "" stays "" (as the theme); anything else is an int clamped to the bounds."""
    if value is None or str(value).strip() == "":
        return ""
    try:
        return _clamp(int(value), bounds)
    except (TypeError, ValueError):
        return ""


def resolve_display(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Type and bound a raw key → value mapping (strings from the table or a query string).

    Missing keys take the defaults. A known preset wins over rows/cols; `custom` (or any unknown
    preset) uses rows/cols clamped to the bounds.
    """
    merged: dict[str, Any] = {**DEFAULT_SETTINGS, **{k: v for k, v in raw.items() if v is not None}}
    preset = str(merged["grid_preset"]).strip().lower()
    if preset in PRESETS:
        rows, cols = PRESETS[preset]
    else:
        preset = "custom"
        rows = _clamp(_as_int(merged["rows"], int(DEFAULT_SETTINGS["rows"])), ROWS_BOUNDS)
        cols = _clamp(_as_int(merged["cols"], int(DEFAULT_SETTINGS["cols"])), COLS_BOUNDS)
    return {
        "grid_preset": preset,
        "rows": rows,
        "cols": cols,
        "animation": _clamp(
            _as_int(merged["animation"], int(DEFAULT_SETTINGS["animation"])), ANIMATION_BOUNDS
        ),
        "sound_enabled": _as_bool(merged["sound_enabled"]),
        "sound_volume": min(1.0, max(0.0, _as_float(merged["sound_volume"], 0.6))),
        "theme": str(merged["theme"]).strip() or DEFAULT_SETTINGS["theme"],
        "poll_seconds": _as_int(merged["poll_seconds"], int(DEFAULT_SETTINGS["poll_seconds"])),
        "rotate_seconds": _as_int(
            merged["rotate_seconds"], int(DEFAULT_SETTINGS["rotate_seconds"])
        ),
        "idle_text": str(merged["idle_text"]),
        "timer_ring": (
            str(merged["timer_ring"]).strip().lower()
            if str(merged["timer_ring"]).strip().lower() in TIMER_RINGS
            else DEFAULT_SETTINGS["timer_ring"]
        ),
        "background_image": str(merged["background_image"] or "").strip(),
        "background_blur": _clamp(_as_int(merged["background_blur"], 12), (0, 40)),
        "background_dim": _clamp(_as_int(merged["background_dim"], 30), (0, 90)),
        "background_fit": (
            "contain" if str(merged["background_fit"]).strip().lower() == "contain" else "cover"
        ),
        **{
            key: _clamp(_as_int(merged[key], int(DEFAULT_SETTINGS[key])), bounds)
            for key, bounds in FLAP_BOUNDS.items()
        },
        "cell_depth": _opt_int(merged["cell_depth"], CELL_DEPTH_BOUNDS),
        "frame_color": _as_color(merged["frame_color"]),
        "frame_width": _opt_int(merged["frame_width"], FRAME_BOUNDS["frame_width"]),
        "frame_radius": _opt_int(merged["frame_radius"], FRAME_BOUNDS["frame_radius"]),
        "frame_finish": (
            str(merged["frame_finish"]).strip().lower()
            if str(merged["frame_finish"]).strip().lower() in FRAME_FINISHES
            else DEFAULT_SETTINGS["frame_finish"]
        ),
        "frame_glow": _as_color(merged["frame_glow"]),
        "frame_fit": (
            str(merged["frame_fit"]).strip().lower()
            if str(merged["frame_fit"]).strip().lower() in FRAME_FITS
            else DEFAULT_SETTINGS["frame_fit"]
        ),
        **{
            key: _clamp(_as_int(merged[key], int(DEFAULT_SETTINGS[key])), bounds)
            for key, bounds in BOARD_BOUNDS.items()
        },
        "guest_token": str(merged["guest_token"] or "").strip(),
        "guest_auto_approve": _as_bool(merged["guest_auto_approve"]),
        "setup_done": "1" if str(merged["setup_done"] or "").strip() == "1" else "",
        "active_profile": str(merged["active_profile"] or "").strip(),
        "calendar_everyday": str(merged["calendar_everyday"] or "").strip(),
        "calendar_applied": str(merged["calendar_applied"] or "").strip(),
        **{
            key: _clamp(_as_int(merged[key], int(DEFAULT_SETTINGS[key])), bounds)
            for key, bounds in GUEST_BOUNDS.items()
        },
    }


def display_settings(session: Session) -> dict[str, Any]:
    """The settings table, typed and bounded, with defaults for whatever is not stored."""
    stored = {row.key: row.value for row in session.scalars(select(Setting))}
    return resolve_display(stored)
