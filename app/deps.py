"""FastAPI dependencies shared by the routers."""

from collections.abc import Iterator
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from fastapi import Request
from sqlalchemy.orm import Session

from app.config import Settings


def get_session(request: Request) -> Iterator[Session]:
    yield from request.app.state.db.session()


def now(request: Request) -> datetime:
    """The current instant (UTC). Tests replace app.state.clock."""
    clock = getattr(request.app.state, "clock", None)
    return clock() if clock else datetime.now(UTC)


def app_settings(request: Request) -> Settings:
    return request.app.state.settings


def tz(request: Request) -> ZoneInfo:
    return ZoneInfo(request.app.state.settings.tz)
