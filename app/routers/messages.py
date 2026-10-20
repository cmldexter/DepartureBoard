"""Messages: everything the settings page does, one curl away. Bearer token on every route."""

from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.deps import get_session, now, tz
from app.models import Message
from app.schemas import MessageIn, MessageOut, MessagePatch, NowIn, PreviewIn, PreviewOut, State
from app.services import images
from app.services.auth import Authenticated
from app.services.display import display_settings
from app.services.scheduler import as_utc
from app.services.scheduler import state as message_state
from app.services.text import capacity_error, layout

router = APIRouter(prefix="/api/messages", tags=["messages"], dependencies=[Authenticated])


def check_text(text: str, session: Session, settings: Settings):
    """422 with a readable reason when the text does not fit or names an unknown image."""
    d = display_settings(session)
    lay = layout(text, d["rows"], d["cols"])
    if err := capacity_error(lay):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, err)
    missing = [s for s in lay.images if images.find(settings, s) is None]
    if missing:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"Unknown image {', '.join('{img:' + s + '}' for s in missing)}. "
            "Upload it first: POST /api/images.",
        )
    return lay


def to_out(m: Message, session: Session, at: datetime, zone: ZoneInfo) -> MessageOut:
    d = display_settings(session)
    lay = layout(m.text, d["rows"], d["cols"])
    fields = {k: getattr(m, k) for k in MessageOut.model_fields if hasattr(m, k)}
    for k in ("starts_at", "ends_at", "created_at", "updated_at"):
        fields[k] = as_utc(fields[k])  # SQLite returns naive; they are UTC
    return MessageOut(
        **fields,
        state=message_state(m, at, zone),
        rows=lay.rows,
        used=lay.used,
        capacity=lay.capacity,
        unknown=sorted(set(lay.unknown)),
    )


def _source(request: Request) -> str:
    return "ui" if request.cookies.get("db_session") else "api"


@router.get("", summary="List messages", response_model=list[MessageOut])
def list_messages(
    state: State | None = Query(None, description="Only messages in this state"),
    session: Session = Depends(get_session),
    at: datetime = Depends(now),
    zone: ZoneInfo = Depends(tz),
):
    rows = session.scalars(select(Message).order_by(Message.id)).all()
    out = [to_out(m, session, at, zone) for m in rows]
    return [o for o in out if state is None or o.state == state]


@router.post(
    "", summary="Create a message", response_model=MessageOut, status_code=status.HTTP_201_CREATED
)
def create_message(
    body: MessageIn,
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
    at: datetime = Depends(now),
    zone: ZoneInfo = Depends(tz),
):
    check_text(body.text, session, request.app.state.settings)
    m = Message(**body.model_dump(), source=_source(request))
    session.add(m)
    session.commit()
    session.refresh(m)
    response.headers["Location"] = f"/api/messages/{m.id}"
    return to_out(m, session, at, zone)


@router.post(
    "/now",
    summary="Show this now",
    description="Text only. Live immediately, above everything else that is live.",
    response_model=MessageOut,
    status_code=status.HTTP_201_CREATED,
)
def post_now(
    body: NowIn,
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
    at: datetime = Depends(now),
    zone: ZoneInfo = Depends(tz),
):
    check_text(body.text, session, request.app.state.settings)
    top = max((m.priority for m in session.scalars(select(Message))), default=0)
    m = Message(
        text=body.text,
        priority=min(100, top + 1),
        source=_source(request),
        created_by=body.created_by,
    )
    session.add(m)
    session.commit()
    session.refresh(m)
    response.headers["Location"] = f"/api/messages/{m.id}"
    return to_out(m, session, at, zone)


@router.post(
    "/preview",
    summary="Preview a text on the board",
    description="Nothing is stored. The organizer calls this as you type.",
    response_model=PreviewOut,
)
def preview(body: PreviewIn, request: Request, session: Session = Depends(get_session)):
    d = display_settings(session)
    lay = layout(body.text, d["rows"], d["cols"])
    settings = request.app.state.settings
    return PreviewOut(
        rows=lay.rows,
        grid_rows=d["rows"],
        grid_cols=d["cols"],
        used=lay.used,
        capacity=lay.capacity,
        overflow=lay.overflow,
        unknown=sorted(set(lay.unknown)),
        missing_images=sorted({s for s in lay.images if images.find(settings, s) is None}),
    )


def _get(message_id: int, session: Session) -> Message:
    m = session.get(Message, message_id)
    if m is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such message.")
    return m


@router.get("/{message_id}", summary="Read a message", response_model=MessageOut)
def read_message(
    message_id: int,
    session: Session = Depends(get_session),
    at: datetime = Depends(now),
    zone: ZoneInfo = Depends(tz),
):
    return to_out(_get(message_id, session), session, at, zone)


@router.patch("/{message_id}", summary="Edit a message", response_model=MessageOut)
def patch_message(
    message_id: int,
    body: MessagePatch,
    request: Request,
    session: Session = Depends(get_session),
    at: datetime = Depends(now),
    zone: ZoneInfo = Depends(tz),
):
    m = _get(message_id, session)
    changes = body.model_dump(exclude_unset=True)
    if "text" in changes:
        check_text(changes["text"], session, request.app.state.settings)
    for k, v in changes.items():
        setattr(m, k, v)
    try:
        MessageIn.model_validate({f: getattr(m, f) for f in MessageIn.model_fields})
    except ValueError as e:
        session.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from e
    session.commit()
    session.refresh(m)
    return to_out(m, session, at, zone)


@router.delete("/{message_id}", summary="Delete a message", status_code=status.HTTP_204_NO_CONTENT)
def delete_message(message_id: int, session: Session = Depends(get_session)):
    session.delete(_get(message_id, session))
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
