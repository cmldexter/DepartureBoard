"""A fixture extension: everything app/extensions.py offers, exercised once (tests/test_extensions.py).

Registered by monkeypatching the entry points — it is never installed, never in the image."""

from pathlib import Path

from fastapi import APIRouter, FastAPI

from app.extensions import BoardSource
from app.services.auth import Authenticated

HERE = Path(__file__).resolve().parent

router = APIRouter(prefix="/api/hello", tags=["hello"])


@router.get("", summary="The fixture says hello")
def hello() -> dict[str, str]:
    return {"hello": "world"}


@router.get("/private", dependencies=[Authenticated], summary="The core's auth, reused")
def private() -> dict[str, bool]:
    return {"ok": True}


# the board source the tests drive: text → it has the board; None → the rotation; raise → skipped
CAPTION: dict = {"text": None, "seconds": None, "remaining": None, "poll": None, "raise": False}


def caption(session, at, display):
    if CAPTION["raise"]:
        raise RuntimeError("source boom")
    if CAPTION["text"] is None and not CAPTION.get("standby"):
        return None
    return BoardSource(
        CAPTION["text"], CAPTION["seconds"], CAPTION["remaining"], True, CAPTION["poll"]
    )


async def start(app: FastAPI) -> None:
    app.state.hello_started = True


async def stop(app: FastAPI) -> None:
    app.state.hello_stopped = True


def register(app: FastAPI, hooks) -> None:
    hooks.router(router)
    hooks.templates(HERE / "templates")
    hooks.static("hello", HERE / "static")
    hooks.tab("hello", "Hello", "hello_panel.html", script="hello.js", style="hello.css", order=10)
    hooks.migrations(HERE / "migrations")
    hooks.on_startup(start)
    hooks.on_shutdown(stop)
    hooks.board_source(caption)
    hooks.edition("TEST")


def register_broken(app: FastAPI, hooks) -> None:
    """Registers half a tab, then fails: nothing of it may remain."""
    hooks.tab("broken", "Broken", "broken.html")
    raise RuntimeError("boom")
