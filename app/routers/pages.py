"""The HTML pages: the board, the settings page, the integrate page."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

from app.services.auth import COOKIE_NAME, _presented_token, token_matches
from app.services.display import display_settings, resolve_display

router = APIRouter(include_in_schema=False)


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
    """
    with next(request.app.state.db.session()) as session:
        display = display_settings(session)
    demo = "demo" in request.query_params
    if demo:
        overrides = {key: request.query_params.get(key) for key in ("rows", "cols", "animation")}
        if "preset" in request.query_params:
            overrides["grid_preset"] = request.query_params["preset"]
        elif "rows" in request.query_params or "cols" in request.query_params:
            overrides["grid_preset"] = "custom"
        display = resolve_display({**display, **overrides})
    rows, cols = display["rows"], display["cols"]
    config = {
        "rows": rows,
        "cols": cols,
        "animation": display["animation"],
        "demo": demo,
    }
    return request.app.state.templates.TemplateResponse(
        request,
        "board.html",
        {"rows": rows, "cols": cols, "grid": _placeholder_rows(rows, cols), "config": config},
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
            "themes": ["classic-black", "walnut", "arctic-white", "midnight"],
        },
    )


@router.post("/settings/login")
def settings_login(request: Request, token: str = Form(...)):
    if not token_matches(request, token.strip()):
        return request.app.state.templates.TemplateResponse(
            request,
            "login.html",
            {"error": "That token did not match."},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    response = RedirectResponse("/settings", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        COOKIE_NAME, token.strip(), httponly=True, samesite="lax", max_age=60 * 60 * 24 * 365
    )
    return response


@router.post("/settings/logout")
def settings_logout():
    response = RedirectResponse("/settings", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(COOKIE_NAME)
    return response
