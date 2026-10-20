"""What the board shows now. Public, so the TV never holds a secret; cheap, so many can poll."""

import hashlib
import json
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.deps import get_session, now, tz
from app.schemas import BoardCurrent, BoardSettings
from app.services.display import display_settings
from app.services.scheduler import live_messages, rotation
from app.services.text import layout, padded_rows

router = APIRouter(prefix="/api/board", tags=["board"])


def current_board(session: Session, at: datetime, zone: ZoneInfo) -> BoardCurrent:
    d = display_settings(session)
    live = live_messages(session, at, zone)
    chosen = rotation(live, at, d["rotate_seconds"])
    text = chosen.text if chosen else d["idle_text"]
    rows = padded_rows(layout(text, d["rows"], d["cols"]))
    settings = BoardSettings(**{k: d[k] for k in BoardSettings.model_fields})
    digest = hashlib.sha256(
        json.dumps(
            [chosen.id if chosen else None, rows, settings.model_dump()], sort_keys=True
        ).encode()
    ).hexdigest()[:16]
    return BoardCurrent(
        stamp=digest, message_id=chosen.id if chosen else None, rows=rows, settings=settings
    )


@router.get(
    "/current",
    summary="What the board shows now",
    description=(
        "The live message (rotating among equals every `rotate_seconds`, the same for every "
        "screen), or the idle text, laid out as rows × cols cells, with the display settings. "
        "Send `If-None-Match` with the last `ETag` to get `304` when nothing changed."
    ),
    response_model=BoardCurrent,
    responses={304: {"description": "Nothing changed since that ETag"}},
)
def board_current(
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
    at: datetime = Depends(now),
    zone: ZoneInfo = Depends(tz),
):
    board = current_board(session, at, zone)
    etag = f'"{board.stamp}"'
    if request.headers.get("if-none-match", "").replace("W/", "") == etag:
        return Response(status_code=304, headers={"ETag": etag, "Cache-Control": "no-cache"})
    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = "no-cache"
    return board
