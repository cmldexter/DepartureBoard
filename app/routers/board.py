"""What the board shows now. Public, so the TV never holds a secret; cheap, so many can poll."""

import hashlib
import json
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.config import Settings
from app.deps import app_settings, get_session, now, tz
from app.extensions import Provider, ask_sources
from app.schemas import BoardCurrent, BoardSettings, BoardTimer
from app.services import images
from app.services.display import display_settings
from app.services.scheduler import Slot, live_messages, rotation_slot
from app.services.text import layout, padded_rows

router = APIRouter(prefix="/api/board", tags=["board"])


def current_board(
    session: Session,
    at: datetime,
    zone: ZoneInfo,
    settings: Settings,
    sources: list[tuple[str, Provider]] = (),  # type: ignore[assignment]
) -> BoardCurrent:
    d = display_settings(session)
    # A transient source (an extension's, app/extensions.py) is asked first: when it has rows
    # they take the board for its slot, no message written; otherwise the rotation as always.
    source = ask_sources(list(sources), session, at, d)
    if source is not None:
        chosen = None
        text = source.text
        slot = Slot(None, source.seconds, source.remaining, source.own)
    else:
        live = live_messages(session, at, zone)
        slot = rotation_slot(live, at, d["rotate_seconds"])
        chosen = slot.message
        text = chosen.text if chosen else d["idle_text"]
    poll = source.poll if source is not None else None
    rows = padded_rows(layout(text, d["rows"], d["cols"], images.sizes(settings)))
    settings = BoardSettings(**{k: d[k] for k in BoardSettings.model_fields})
    # The slot's length and ownership are constant within a slot, so they belong in the stamp
    # (rotating → alone must change the ETag); the seconds left do not. A source's poll hint
    # joins only when there is one, so the stamp is what it was for everyone else.
    stamped = [chosen.id if chosen else None, rows, settings.model_dump(), slot.seconds, slot.own]
    if poll:
        stamped.append(poll)
    digest = hashlib.sha256(json.dumps(stamped, sort_keys=True).encode()).hexdigest()[:16]
    timer = (
        BoardTimer(seconds=slot.seconds, remaining=slot.remaining, own=slot.own)
        if slot.seconds is not None and slot.remaining is not None
        else None
    )
    return BoardCurrent(
        stamp=digest,
        message_id=chosen.id if chosen else None,
        rows=rows,
        settings=settings,
        timer=timer,
        **({"poll": poll} if poll else {}),  # unset, not null, when no source hints
    )


@router.get(
    "/current",
    summary="What the board shows now",
    description=(
        "The live message (equals take turns, each for its own `show_seconds` or the display's "
        "`rotate_seconds`, in step on every screen), or the idle text, laid out as rows × cols "
        "cells, with the display settings. While messages rotate, `timer` says how long the "
        "slot is and how much is left; it is not part of the `ETag`. Send `If-None-Match` with "
        "the last `ETag` to get `304` when nothing changed. `poll` appears only while a "
        "transient source has the board and asks for a quicker return."
    ),
    response_model=BoardCurrent,
    response_model_exclude_unset=True,
    responses={304: {"description": "Nothing changed since that ETag"}},
)
def board_current(
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
    at: datetime = Depends(now),
    zone: ZoneInfo = Depends(tz),
    settings: Settings = Depends(app_settings),
):
    board = current_board(session, at, zone, settings, request.app.state.ext.sources)
    etag = f'"{board.stamp}"'
    if request.headers.get("if-none-match", "").replace("W/", "") == etag:
        return Response(status_code=304, headers={"ETag": etag, "Cache-Control": "no-cache"})
    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = "no-cache"
    return board
