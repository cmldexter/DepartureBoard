"""A calendar of boards: saved boards assigned to date ranges, kept in <data_dir>/calendar.json
beside the profiles, and the switch that puts the planned board on the TV at the day boundary —
after saving the live board back into its own profile, so nothing is ever lost."""

import json
import logging
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Message, Setting
from app.services import profiles
from app.services.display import display_settings

log = logging.getLogger("departureboard.calendar")
FILE = "calendar.json"


@dataclass
class Entry:
    id: int
    profile: str
    start: date
    end: date | None  # inclusive; None = open-ended
    note: str = ""

    def covers(self, day: date) -> bool:
        return self.start <= day and (self.end is None or day <= self.end)


def path_of(settings: Settings) -> Path:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return settings.data_dir / FILE


def read(settings: Settings) -> list[Entry]:
    path = path_of(settings)
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text())
        return [
            Entry(
                id=int(e["id"]),
                profile=str(e["profile"]),
                start=date.fromisoformat(e["start"]),
                end=date.fromisoformat(e["end"]) if e.get("end") else None,
                note=str(e.get("note") or ""),
            )
            for e in raw.get("entries", [])
        ]
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as e:
        log.warning("calendar.json unreadable, treated as empty: %s", e)
        return []


def write(settings: Settings, entries: list[Entry]) -> None:
    data = {"entries": [_json(e) for e in sorted(entries, key=lambda e: (e.start, e.id))]}
    path_of(settings).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def _json(e: Entry) -> dict[str, Any]:
    d = asdict(e)
    d["start"] = e.start.isoformat()
    d["end"] = e.end.isoformat() if e.end else None
    return d


def covering(entries: list[Entry], day: date, settings: Settings) -> Entry | None:
    """The entry for `day`: the latest start wins (a one-day entry inside a long one shows that
    day), ties by id; an entry whose board was deleted is skipped."""
    due = [e for e in entries if e.covers(day) and profiles.find(settings, e.profile)]
    return max(due, key=lambda e: (e.start, e.id)) if due else None


def add(settings: Settings, profile: str, start: date, end: date | None, note: str) -> Entry:
    entries = read(settings)
    entry = Entry(max((e.id for e in entries), default=0) + 1, profile, start, end, note)
    write(settings, [*entries, entry])
    return entry


def update(settings: Settings, entry: Entry) -> None:
    entries = [entry if e.id == entry.id else e for e in read(settings)]
    write(settings, entries)


def remove(settings: Settings, entry_id: int) -> bool:
    entries = read(settings)
    kept = [e for e in entries if e.id != entry_id]
    if len(kept) == len(entries):
        return False
    write(settings, kept)
    return True


def today_of(at: datetime, zone: ZoneInfo) -> date:
    return at.astimezone(zone).date()


def plan_for(
    entries: list[Entry], day: date, everyday: str, settings: Settings
) -> tuple[str, str | None, Entry | None]:
    """What the board should be on `day`: (key, profile, entry). The key names what was
    decided, so the tick can tell a change from a repeat."""
    entry = covering(entries, day, settings)
    if entry:
        return f"entry:{entry.id}:{entry.profile}", entry.profile, entry
    if everyday and profiles.find(settings, everyday):
        return f"everyday:{everyday}", everyday, None
    return "", None, None


def tick(session: Session, settings: Settings, at: datetime, zone: ZoneInfo) -> dict[str, Any]:
    """Put the planned board on the TV if the plan changed since the last tick.

    Order: the live board is saved back into its active profile (or, with no active profile and
    messages on it, into `unsaved-<date>`), then the planned board is loaded, then
    `calendar_applied` remembers the decision. Commits. Returns what happened."""
    d = display_settings(session)
    day = today_of(at, zone)
    key, target, entry = plan_for(read(settings), day, d["calendar_everyday"], settings)
    out: dict[str, Any] = {
        "changed": False,
        "applied": key,
        "loaded": None,
        "saved_back": None,
        "kept_disabled": [],
    }
    if key == d["calendar_applied"]:
        return out
    if target:
        active = d["active_profile"]
        if active and profiles.find(settings, active):
            profiles.save(settings, session, active, None, at)
            out["saved_back"] = active
        elif not active and session.scalar(select(func.count(Message.id))):
            slug = f"unsaved-{day.isoformat()}"
            profiles.save(settings, session, slug, f"Unsaved board {day.isoformat()}", at)
            out["saved_back"] = slug
        path = profiles.find(settings, target)
        assert path is not None
        _, kept = profiles.load(settings, session, path, "api")
        out.update(changed=True, loaded=target, kept_disabled=kept)
        log.info("calendar: %s on the board (%s)", target, key)
    session.merge(Setting(key="calendar_applied", value=key))
    session.commit()
    return out


def run_tick(app: Any) -> dict[str, Any]:
    """One tick from the background loop: the app's clock (tests inject it) and timezone."""
    clock = getattr(app.state, "clock", None)
    at = clock() if clock else datetime.now(UTC)
    with next(app.state.db.session()) as session:
        return tick(session, app.state.settings, at, ZoneInfo(app.state.settings.tz))
