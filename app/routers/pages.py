"""The HTML pages: the board, the settings page, the integrate page."""

from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Form, Request, status
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse

from app import __version__
from app.models import THEMES
from app.services.auth import COOKIE_NAME, _presented_token, token_matches
from app.services.display import display_settings, resolve_display
from app.services.tls import local_ipv4s

router = APIRouter(include_in_schema=False)
LLMS_TXT = Path(__file__).resolve().parent.parent.parent / "llms.txt"
_LOOPBACK = {"localhost", "127.0.0.1", "::1"}


def board_addresses(request: Request) -> list[dict[str, str]]:
    """Where the board can be opened, as `{label, url}`: the name the owner gave it
    (DEPARTUREBOARD_HOST) first, then the address this request came on, then the addresses this
    server sees on its own interfaces (inside a container those are the container's, not the
    LAN's). The scheme and port are the request's: the port the browser used is the published
    one, whatever the container listens on."""
    scheme, port = request.url.scheme, request.url.port
    suffix = f":{port}" if port else ""
    name = request.app.state.settings.host
    entries: list[tuple[str, str]] = []
    if name:
        entries.append(("by name", name))
    here = request.url.hostname or ""
    if here and here not in _LOOPBACK and here != name:
        entries.append(("the address you are using", here))
    entries.extend(("as this server sees it", ip) for ip in local_ipv4s())
    out: list[dict[str, str]] = []
    for label, host in entries:
        url = f"{scheme}://{host}{suffix}"
        if all(e["url"] != url for e in out):
            out.append({"label": label, "url": url})
    return out


def _placeholder_rows(rows: int, cols: int) -> list[str]:
    """What the board shows before any message exists: the name and where to go next."""
    grid = [" " * cols for _ in range(rows)]
    grid[rows // 2 - 1] = "DEPARTUREBOARD".center(cols)
    grid[rows // 2] = "SET UP AT /SETTINGS".center(cols)
    return grid


@router.get("/", response_class=HTMLResponse)
def board(request: Request):
    """The board. Display settings come from the settings table.

    `?demo` shows built-in messages so the board can be seen before any message exists; in demo
    mode only, `preset`, `rows`, `cols` and `animation` may be overridden in the query string.

    `?embed` is the board for a frame on the settings page: no HUD, no fullscreen, no wake lock,
    no sound, still polling. `?embed&preview` is the same page as a renderer only: a blank grid
    that never polls (and never runs the demo); the settings page posts rows and settings into it.
    """
    with next(request.app.state.db.session()) as session:
        display = display_settings(session)
    embed = "embed" in request.query_params
    preview = "preview" in request.query_params
    demo = "demo" in request.query_params and not preview
    if demo:
        overrides = {
            key: request.query_params.get(key) for key in ("rows", "cols", "animation", "theme")
        }
        if "preset" in request.query_params:
            overrides["grid_preset"] = request.query_params["preset"]
        elif "rows" in request.query_params or "cols" in request.query_params:
            overrides["grid_preset"] = "custom"
        display = resolve_display({**display, **overrides})
    rows, cols = display["rows"], display["cols"]
    theme = display["theme"] if display["theme"] in THEMES else THEMES[0]
    config = {
        "rows": rows,
        "cols": cols,
        "animation": display["animation"],
        "sound_enabled": display["sound_enabled"],
        "sound_volume": display["sound_volume"],
        "theme": theme,
        "poll_seconds": display["poll_seconds"],
        "timer_ring": display["timer_ring"],
        "background_image": display["background_image"],
        "background_blur": display["background_blur"],
        "background_dim": display["background_dim"],
        "background_fit": display["background_fit"],
        "demo": demo,
        "embed": embed,
        "preview": preview,
    }
    grid = [" " * cols for _ in range(rows)] if preview else _placeholder_rows(rows, cols)
    return request.app.state.templates.TemplateResponse(
        request,
        "board.html",
        {
            "rows": rows,
            "cols": cols,
            "grid": grid,
            "config": config,
            "theme": theme,
            "embed": embed,
        },
    )


@router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request):
    templates = request.app.state.templates
    if not token_matches(request, _presented_token(request)):
        return templates.TemplateResponse(
            request, "login.html", {}, status_code=status.HTTP_401_UNAUTHORIZED
        )
    settings = request.app.state.settings
    now = datetime.now(UTC).astimezone(ZoneInfo(settings.tz))
    return templates.TemplateResponse(
        request,
        "settings.html",
        {
            "token": request.app.state.api_token,
            "tz": settings.tz,
            "server_time": now.strftime("%Y-%m-%d %H:%M"),
            "themes": list(THEMES),
            "addresses": board_addresses(request),
            "named": bool(settings.host),
        },
    )


@router.get("/integrate", response_class=HTMLResponse)
def integrate_page(request: Request):
    """Copy-paste lines filled with this host and this install's token. Same cookie as settings.
    The host is the board's name when it has one, else whatever the browser used to get here."""
    templates = request.app.state.templates
    if not token_matches(request, _presented_token(request)):
        return templates.TemplateResponse(
            request, "login.html", {"next": "/integrate"}, status_code=status.HTTP_401_UNAUTHORIZED
        )
    base = str(request.base_url).rstrip("/")
    if request.app.state.settings.host:
        base = board_addresses(request)[0]["url"]
    return templates.TemplateResponse(
        request,
        "integrate.html",
        {"token": request.app.state.api_token, "base_url": base, "version": __version__},
    )


@router.get("/llms.txt", response_class=PlainTextResponse)
def llms_txt():
    """The repo's llms.txt, for anything that reads the web before acting."""
    return PlainTextResponse(LLMS_TXT.read_text(), media_type="text/plain; charset=utf-8")


@router.post("/settings/login")
def settings_login(request: Request, token: str = Form(...), next: str = Form("/settings")):
    if not token_matches(request, token.strip()):
        return request.app.state.templates.TemplateResponse(
            request,
            "login.html",
            {"error": "That token did not match.", "next": next},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    target = next if next in ("/settings", "/integrate") else "/settings"
    response = RedirectResponse(target, status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        COOKIE_NAME,
        token.strip(),
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
        max_age=60 * 60 * 24 * 365,
    )
    return response


@router.post("/settings/logout")
def settings_logout():
    response = RedirectResponse("/settings", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(COOKIE_NAME)
    return response
