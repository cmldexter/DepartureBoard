"""Which messages are live right now.

Pure over the rows: `now` is injected, so the table-driven tests can pick any instant. All
timestamps are stored in UTC; the repeat rules are evaluated in the configured timezone.
"""

from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Message

State = str  # live | scheduled | expired | disabled


def as_utc(dt: datetime | None) -> datetime | None:
    """SQLite hands naive datetimes back; they were stored as UTC."""
    if dt is None:
        return None
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def _hhmm(value: str) -> time:
    h, m = value.split(":")
    return time(int(h), int(m))


def in_window(m: Message, now: datetime) -> bool:
    starts, ends = as_utc(m.starts_at), as_utc(m.ends_at)
    if starts and now < starts:
        return False
    if ends and now > ends:
        return False
    return True


def repeat_matches(m: Message, now: datetime, tz: ZoneInfo) -> bool:
    """Does the daily/weekly rule include `now`? `none` always does."""
    if m.repeat == "none":
        return True
    local = now.astimezone(tz)
    day = local.date()
    if m.repeat_start and m.repeat_end:
        start, end = _hhmm(m.repeat_start), _hhmm(m.repeat_end)
        t = local.time().replace(second=0, microsecond=0)
        if start <= end:
            in_time = start <= t < end
        else:  # crosses midnight: 22:00–06:00
            in_time = t >= start or t < end
            if t < end:  # the after-midnight part belongs to the day the window started
                day = day - timedelta(days=1)
        if not in_time:
            return False
    if m.repeat == "weekly":
        return bool(m.repeat_days & (1 << day.weekday()))
    return True


def is_live(m: Message, now: datetime, tz: ZoneInfo) -> bool:
    return bool(m.enabled) and in_window(m, now) and repeat_matches(m, now, tz)


def state(m: Message, now: datetime, tz: ZoneInfo) -> State:
    if not m.enabled:
        return "disabled"
    if is_live(m, now, tz):
        return "live"
    ends = as_utc(m.ends_at)
    if ends and now > ends:
        return "expired"
    return "scheduled"


def live_messages(session: Session, now: datetime, tz: ZoneInfo) -> list[Message]:
    """Live messages, highest priority first, oldest first within a priority."""
    rows = session.scalars(select(Message).where(Message.enabled.is_(True))).all()
    live = [m for m in rows if is_live(m, now, tz)]
    return sorted(live, key=lambda m: (-m.priority, m.id))


def rotation(live: list[Message], now: datetime, rotate_seconds: int) -> Message | None:
    """The message to show: the top-priority group rotates every `rotate_seconds`.

    Stateless — `(now // rotate_seconds) % len(group)` — so every screen polling the server
    shows the same message at the same moment.
    """
    if not live:
        return None
    top = [m for m in live if m.priority == live[0].priority]
    index = (int(now.timestamp()) // max(1, rotate_seconds)) % len(top)
    return top[index]
