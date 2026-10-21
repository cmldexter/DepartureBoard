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

router = APIRouter(include_in_schema=False)
LLMS_TXT = Path(__file__).resolve().parent.parent.parent / "llms.txt"


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
    tz = request.app.state.settings.tz
    now = datetime.now(UTC).astimezone(ZoneInfo(tz))
    return templates.TemplateResponse(
        request,
        "settings.html",
        {
            "token": request.app.state.api_token,
            "tz": tz,
            "server_time": now.strftime("%Y-%m-%d %H:%M"),
            "themes": list(THEMES),
        },
    )


@router.get("/integrate", response_class=HTMLResponse)
def integrate_page(request: Request):
    """Copy-paste lines filled with this host and this install's token. Same cookie as settings."""
    templates = request.app.state.templates
    if not token_matches(request, _presented_token(request)):
        return templates.TemplateResponse(
            request, "login.html", {"next": "/integrate"}, status_code=status.HTTP_401_UNAUTHORIZED
        )
    base = str(request.base_url).rstrip("/")
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
        COOKIE_NAME, token.strip(), httponly=True, samesite="lax", max_age=60 * 60 * 24 * 365
    )
    return response


@router.post("/settings/logout")
def settings_logout():
    response = RedirectResponse("/settings", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(COOKIE_NAME)
    return response
