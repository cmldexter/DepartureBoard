"""The display settings the board page needs, typed and bounded.

Reads the `settings` table, overlays the defaults, and resolves the grid preset into rows and
columns. Pure over a session so the board page, and later the board and settings APIs, share it.
"""

from collections.abc import Mapping
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import COLS_BOUNDS, DEFAULT_SETTINGS, PRESETS, ROWS_BOUNDS, TIMER_RINGS, Setting

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
    }


def display_settings(session: Session) -> dict[str, Any]:
    """The settings table, typed and bounded, with defaults for whatever is not stored."""
    stored = {row.key: row.value for row in session.scalars(select(Setting))}
    return resolve_display(stored)
