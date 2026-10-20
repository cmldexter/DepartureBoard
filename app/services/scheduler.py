"""Which messages are live right now. Epic 4 fills this in; the placeholder does not need it."""

from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Message


def live_messages(session: Session, now: datetime) -> list[Message]:  # pragma: no cover
    """Return the messages whose window and repeat rule include `now`, highest priority first."""
    raise NotImplementedError("Scheduling arrives in Epic 4.")
