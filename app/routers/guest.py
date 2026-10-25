"""The guest link. `public` is the phone page — the one write path without the bearer token,
guarded by the token in its URL, reaching nothing but the post queue. `api` manages the link."""

from datetime import UTC, datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.deps import app_settings, get_session, now, tz
from app.models import Post, Setting
from app.routers.pages import board_addresses
from app.schemas import GuestLink, GuestQr
from app.services import guest, images
from app.services.auth import Authenticated
from app.services.display import display_settings
from app.services.exif import strip
from app.services.imagesize import dimensions
from app.services.scheduler import state as message_state

api = APIRouter(prefix="/api/guest", tags=["guests"], dependencies=[Authenticated])
public = APIRouter(include_in_schema=False)


@api.post(
    "/rotate",
    summary="Mint a new guest link",
    description=(
        "Makes a fresh 20-character token, stores it as the display setting `guest_token` and "
        "returns the link to put in a QR code. The old link stops working at once. Close the "
        'door with `PATCH /api/settings {"guest_token": ""}`.'
    ),
    response_model=GuestLink,
)
def rotate(request: Request, session: Session = Depends(get_session)):
    token = guest.mint_token()
    session.merge(Setting(key="guest_token", value=token))
    session.commit()
    url = _link(request, token)
    guest.refresh_qr(request.app.state.settings, url)  # a code on the board follows the link
    return GuestLink(token=token, url=url)


def _link(request: Request, token: str) -> str:
    return f"{board_addresses(request)[0]['url']}/guest/{token}"


@api.post(
    "/qr",
    summary="Put the QR of the guest link on the board",
    description=(
        "Makes (or remakes) the picture `guest-qr` — a QR code of the current guest link, drawn "
        "whole over 4 × 3 cells like any code from `POST /api/images/qr` — and a ready-made "
        "message `SCAN TO POST A PHOTO` + `{img:guest-qr}`, created **disabled** so you switch it "
        "on when the party starts (edit or schedule it like any other). Rotating the link remakes "
        "the code; closing the door disables the message. 409 while guests are off."
    ),
    response_model=GuestQr,
    status_code=status.HTTP_201_CREATED,
    responses={
        200: {"description": "The picture was remade; the message already existed"},
        409: {"description": "Guests are off — make a link first"},
    },
)
def put_qr(
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
    at: datetime = Depends(now),
    zone: ZoneInfo = Depends(tz),
):
    token = display_settings(session)["guest_token"]
    if not token:
        raise HTTPException(status.HTTP_409_CONFLICT, "Guests are off — make a link first.")
    source = "ui" if request.cookies.get("db_session") else "api"
    url = _link(request, token)
    remade, m, created = guest.make_qr(session, request.app.state.settings, url, source)
    session.commit()
    if not created:
        response.status_code = status.HTTP_200_OK
    return GuestQr(
        url=url,
        token=guest.QR_TOKEN,
        message_id=m.id,
        enabled=m.enabled,
        state=message_state(m, at, zone),
    )


def _open_door(token: str, session: Session) -> dict:
    """404 — not 401 — when the link is wrong or guests are off: nothing to learn from the page.
    Returns the display settings (auto-approve decides what the page says)."""
    import secrets

    d = display_settings(session)
    current = d["guest_token"]
    if not current or not secrets.compare_digest(current, token):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    return d


def _page(request: Request, **ctx):
    settings = request.app.state.settings
    return request.app.state.templates.TemplateResponse(
        request,
        "guest.html",
        {
            "name": settings.host or "the board",
            "max_text": guest.MAX_TEXT,
            "max_nick": guest.MAX_NICK,
            **ctx,
        },
        status_code=ctx.pop("code", status.HTTP_200_OK),
    )


@public.get("/guest/{token}", response_class=HTMLResponse)
def guest_page(token: str, request: Request, session: Session = Depends(get_session)):
    d = _open_door(token, session)
    return _page(request, auto=d["guest_auto_approve"])


@public.post("/guest/{token}", response_class=HTMLResponse)
async def guest_post(
    token: str,
    request: Request,
    text: Annotated[str, Form()] = "",
    nick: Annotated[str, Form()] = "",
    photo: Annotated[UploadFile | None, File()] = None,
    session: Session = Depends(get_session),
    at: datetime = Depends(now),
):
    d = _open_door(token, session)
    settings = app_settings(request)
    text = " ".join(text.split())
    nick = " ".join(nick.split())
    form = {"text": text, "nick": nick, "auto": d["guest_auto_approve"]}
    data = b""
    content_type = ""
    if photo is not None and photo.filename:
        content_type = (photo.content_type or "").split(";")[0].strip().lower()
        if content_type not in guest.PHOTO_TYPES:
            return _page(request, error="A photo is a PNG, JPEG or WebP.", code=422, **form)
        data = await photo.read(guest.MAX_PHOTO + 1)
        if len(data) > guest.MAX_PHOTO:
            return _page(request, error="A photo is up to 5 MB.", code=413, **form)
    if not text and not data:
        return _page(request, error="Write a line or add a photo.", code=422, **form)
    if len(text) > guest.MAX_TEXT:
        return _page(request, error=f"Up to {guest.MAX_TEXT} characters.", code=422, **form)
    if len(nick) > guest.MAX_NICK:
        return _page(
            request, error=f"A name is up to {guest.MAX_NICK} characters.", code=422, **form
        )
    ip = guest.ip_hash(request)
    if busy := guest.over_limit(session, at, ip):
        return _page(request, error=busy, code=429, **form)
    post = Post(
        created_at=at.astimezone(UTC).replace(tzinfo=None),
        nick=nick,
        text=text,
        status="pending",
        ip_hash=ip,
    )
    session.add(post)
    session.flush()
    if data:
        clean = strip(data, content_type)
        path, _ = images.save(settings, f"guest-{post.id}", content_type, clean)
        w, h = guest.photo_block(dimensions(clean))
        images.set_size(path, w, h, "contain")
        post.image = path.stem
    live = False
    if d["guest_auto_approve"]:
        message, _ = guest.approve(session, settings, post)
        live = message.enabled
    session.commit()
    return _page(request, done=True, nick=nick, live=live, auto=d["guest_auto_approve"])
