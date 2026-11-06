"""departureboard-hello — the smallest complete extension.

`register(app, hooks)` is what the entry point `departureboard.extensions` names. It adds a
settings tab (a template of ours, a script and a stylesheet served under /static/ext/hello/), a
router under /api/hello behind the board's token, and keeps one key of its own in the settings
table. The core's settings schema is untouched: an extension's keys go through its own router.
"""

from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.deps import get_session
from app.models import Setting
from app.services.auth import Authenticated

HERE = Path(__file__).resolve().parent
KEY = "hello.greeting"  # an extension's keys carry its name; the column holds 40 characters
DEFAULT = "HELLO"

router = APIRouter(prefix="/api/hello", tags=["hello"], dependencies=[Authenticated])


class Greeting(BaseModel):
    greeting: str = Field(min_length=1, max_length=80, examples=["HELLO"])


def read(session: Session) -> str:
    row = session.get(Setting, KEY)
    return row.value if row else DEFAULT


@router.get("", summary="The greeting the Hello tab keeps")
def get_greeting(session: Session = Depends(get_session)) -> Greeting:
    return Greeting(greeting=read(session))


@router.put("", summary="Change it")
def put_greeting(body: Greeting, session: Session = Depends(get_session)) -> Greeting:
    session.merge(Setting(key=KEY, value=body.greeting))
    session.commit()
    return body


def register(app: FastAPI, hooks) -> None:
    hooks.templates(HERE / "templates")
    hooks.static("hello", HERE / "static")
    hooks.tab("hello", "Hello", "hello_tab.html", script="hello.js", style="hello.css")
    hooks.router(router)
