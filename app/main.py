"""DepartureBoard application factory."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import __version__
from app.config import Settings, get_settings
from app.db import Database, migrate
from app.routers import health, pages
from app.services.auth import load_or_create_token

APP_DIR = Path(__file__).resolve().parent

DESCRIPTION = """
An open-source split-flap departure board for any TV.

* `GET /api/board/current` is public — the TV polls it and never holds a secret.
* Everything that writes needs `Authorization: Bearer <token>`.
  The token is printed in the server log on first boot and shown on `/settings`.
"""


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
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.templates = Jinja2Templates(directory=APP_DIR / "templates")
    app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")
    app.include_router(health.router)
    app.include_router(pages.router)
    return app


app = create_app()
