"""The calendar of boards: saved boards assigned to dates, and the switch. Bearer token."""

from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.config import Settings
from app.deps import app_settings, get_session, now, tz
from app.schemas import (
    CalendarApplied,
    CalendarEntryIn,
    CalendarEntryOut,
    CalendarEntryPatch,
    CalendarOut,
    CalendarToday,
)
from app.services import calendar, profiles
from app.services.auth import Authenticated
from app.services.display import display_settings

router = APIRouter(prefix="/api/calendar", tags=["calendar"], dependencies=[Authenticated])


def _out(entry: calendar.Entry, settings: Settings) -> CalendarEntryOut:
    path = profiles.find(settings, entry.profile)
    name = None
    if path is not None:
        try:
            name = profiles.read(path).name
        except ValueError:
            name = None
    return CalendarEntryOut(
        id=entry.id,
        profile=entry.profile,
        name=name,
        start=entry.start,
        end=entry.end,
        note=entry.note,
        missing=path is None,
    )


def _check(profile: str, start, end, settings: Settings) -> None:
    if profiles.find(settings, profile) is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"No saved board {profile!r}. Save one first: POST /api/profiles/{{slug}}/save.",
        )
    if end is not None and end < start:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "end is before start.")


@router.get(
    "",
    summary="The plan",
    description=(
        "Every entry (a saved board for a date range, `end` null = open-ended; `missing` when "
        "its board was deleted), the everyday board, what today resolves to, and what the switch "
        "applied last."
    ),
    response_model=CalendarOut,
)
def read_calendar(
    session: Session = Depends(get_session),
    settings: Settings = Depends(app_settings),
    at: datetime = Depends(now),
    zone: ZoneInfo = Depends(tz),
):
    d = display_settings(session)
    entries = calendar.read(settings)
    day = calendar.today_of(at, zone)
    key, profile, entry = calendar.plan_for(entries, day, d["calendar_everyday"], settings)
    return CalendarOut(
        everyday=d["calendar_everyday"],
        entries=[_out(e, settings) for e in sorted(entries, key=lambda e: (e.start, e.id))],
        today=CalendarToday(
            date=day,
            profile=profile,
            entry_id=entry.id if entry else None,
            until=entry.end if entry else None,
        ),
        applied=d["calendar_applied"],
    )


@router.post(
    "",
    summary="Plan a saved board for a date range",
    description=(
        "Dates are days in the board's timezone; `end` is inclusive, null means until further "
        "notice. When two entries cover a day the later start wins. The switch runs every "
        "30 seconds; `POST /api/calendar/apply` runs it now."
    ),
    response_model=CalendarEntryOut,
    status_code=status.HTTP_201_CREATED,
)
def add_entry(body: CalendarEntryIn, settings: Settings = Depends(app_settings)):
    _check(body.profile, body.start, body.end, settings)
    return _out(calendar.add(settings, body.profile, body.start, body.end, body.note), settings)


def _get(entry_id: int, settings: Settings) -> calendar.Entry:
    for e in calendar.read(settings):
        if e.id == entry_id:
            return e
    raise HTTPException(status.HTTP_404_NOT_FOUND, "No such entry.")


@router.patch("/{entry_id}", summary="Change an entry", response_model=CalendarEntryOut)
def patch_entry(
    entry_id: int, body: CalendarEntryPatch, settings: Settings = Depends(app_settings)
):
    entry = _get(entry_id, settings)
    changes = body.model_dump(exclude_unset=True)
    for k, v in changes.items():
        setattr(entry, k, v)
    _check(entry.profile, entry.start, entry.end, settings)
    calendar.update(settings, entry)
    return _out(entry, settings)


@router.delete("/{entry_id}", summary="Remove an entry", status_code=status.HTTP_204_NO_CONTENT)
def delete_entry(entry_id: int, settings: Settings = Depends(app_settings)):
    if not calendar.remove(settings, entry_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such entry.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/apply",
    summary="Run the switch now",
    description=(
        "What the background tick does every 30 seconds: if the board planned for today differs "
        "from what was applied last, the live board is saved back into its active profile (or "
        "into `unsaved-<date>` when it has no profile and holds messages), the planned board is "
        "loaded, and the decision is remembered in `calendar_applied`."
    ),
    response_model=CalendarApplied,
)
def apply_now(
    session: Session = Depends(get_session),
    settings: Settings = Depends(app_settings),
    at: datetime = Depends(now),
    zone: ZoneInfo = Depends(tz),
):
    return CalendarApplied(**calendar.tick(session, settings, at, zone))
