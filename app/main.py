"""DepartureBoard application factory."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import __version__
from app.config import Settings, get_settings
from app.db import Database, migrate
from app.routers import board, health, images, messages, pages
from app.routers import settings as settings_api
from app.services.auth import load_or_create_token

APP_DIR = Path(__file__).resolve().parent

DESCRIPTION = """
An open-source split-flap departure board for any TV. Everything the settings page does, this
API does — the integrations are yours.

**Auth.** `Authorization: Bearer <token>` on every call except `GET /api/board/current` and
`GET /images/{slug}`, which the TV polls and must never need a secret for. The token is printed
in the server log on first boot and shown on `/settings`.

**The shortest call.** `POST /api/messages/now` with a JSON `{"text": "…"}` or a `text/plain`
body puts a message on the board immediately, above everything else.

**Message text.** Rows split on newlines, else word-wrap to the board's columns. Characters are
uppercased and accents stripped; what the flap set lacks shows as a blank (the response lists
it in `unknown`). Token cells, one cell each: `{red}` `{orange}` `{yellow}` `{green}` `{blue}`
`{violet}` `{white}` `{black}`, any emoji, and `{img:slug}` for a picture uploaded with
`POST /api/images`. Capacity is rows × cols; a message that does not fit is a 422 that says so.

**Schedules.** A window (`starts_at` / `ends_at`, ISO-8601 with offset), a `daily` repeat with a
time of day, or a `weekly` repeat with a weekday mask (Mon=1 … Sun=64, summed). A repeat window
that ends before it starts crosses midnight. When several messages are live the highest priority
shows; equals take turns, each for its own `show_seconds` or the display's `rotate_seconds`, in
step on every screen. The display setting `timer_ring` draws the slot as a small countdown in the
board's corner.

Copy-paste lines pre-filled with your host and token are on `/integrate`. Agents read `/llms.txt`.
"""

TAGS = [
    {"name": "messages", "description": "What the board says and when. Bearer token."},
    {"name": "board", "description": "What the TV shows right now. Public, cheap to poll."},
    {"name": "settings", "description": "Preset, animation, sound, theme, idle text. Token."},
    {
        "name": "images",
        "description": (
            "Pictures for `{img:slug}` cells: uploads, or a QR code the server makes "
            "(`POST /api/images/qr`). Token to write."
        ),
    },
    {"name": "system", "description": "Health."},
]


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        migrate(settings)
        app.state.db = Database(settings)
        app.state.api_token = load_or_create_token(settings)
        yield
        app.state.db.engine.dispose()

    app = FastAPI(
        title="DepartureBoard",
        version=__version__,
        description=DESCRIPTION,
        openapi_tags=TAGS,
        license_info={
            "name": "GPL-3.0-or-later",
            "url": "https://www.gnu.org/licenses/gpl-3.0.html",
        },
        lifespan=lifespan,
    )
    if settings.cors_origin_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origin_list,
            allow_methods=["*"],
            allow_headers=["Authorization", "Content-Type", "If-None-Match"],
        )
    app.state.settings = settings
    app.state.templates = Jinja2Templates(directory=APP_DIR / "templates")
    app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")
    app.include_router(health.router)
    app.include_router(board.router)
    app.include_router(messages.router)
    app.include_router(settings_api.router)
    app.include_router(images.api)
    app.include_router(images.public)
    app.include_router(pages.router)
    return app


app = create_app()
