"""Extension points: another package adds to the board without forking it.

At startup the app looks up the entry-point group ``departureboard.extensions``. Each entry
resolves to a ``register(app, hooks)`` callable; through ``hooks`` the package adds an API router,
a templates directory, a static directory, a settings tab, an Alembic version location, startup
and shutdown tasks, and may name the edition. An extension that fails to load is logged and
skipped — the board never fails to start because of one — and with no extension installed nothing
changes: same pages, same API.

Extensions keep their own settings keys through the settings service; the core's ``SettingsOut``
and ``SettingsPatch`` stay the core's.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime
from importlib.metadata import entry_points
from pathlib import Path
from typing import Any

from fastapi import APIRouter, FastAPI
from sqlalchemy.orm import Session

GROUP = "departureboard.extensions"
BUILTIN_TABS = ("board", "messages", "pictures", "guests", "boards", "setup", "more")
_NAME = re.compile(r"^[a-z][a-z0-9_-]*$")
log = logging.getLogger("departureboard.extensions")

Task = Callable[[FastAPI], Awaitable[None]]


@dataclass(frozen=True)
class BoardSource:
    """What a board source answers when it has something for the board right now — or when it
    wants the TV back soon.

    ``text`` is laid out as a message is (rows × cols, pictures, tokens); ``seconds`` and
    ``remaining`` describe its slot for the timer (both or neither); ``poll`` asks the TV to come
    back in that many seconds instead of its usual ``poll_seconds``. ``text=None`` with a ``poll``
    is a *standby* hint: the rotation shows as always, but the TV polls that often — for a source
    that expects something any moment and wants it on the flaps within a second."""

    text: str | None
    seconds: int | None = None
    remaining: int | None = None
    own: bool = True
    poll: int | None = None


Provider = Callable[[Session, datetime, Mapping[str, Any]], BoardSource | None]


@dataclass(frozen=True)
class Loaded:
    """An extension that registered: what /api/health lists."""

    name: str
    version: str


@dataclass(frozen=True)
class Tab:
    """A settings tab an extension adds: a button in the tab bar, a panel, an optional script."""

    id: str
    label: str
    template: str
    ext: str
    script: str | None = None
    style: str | None = None
    order: int = 100
    icon: str = "puzzle"


@dataclass
class Registry:
    """Everything the loaded extensions asked for, in registration order."""

    loaded: list[Loaded] = field(default_factory=list)
    routers: list[APIRouter] = field(default_factory=list)
    template_dirs: list[Path] = field(default_factory=list)
    static: dict[str, Path] = field(default_factory=dict)
    tabs: list[Tab] = field(default_factory=list)
    migration_dirs: list[Path] = field(default_factory=list)
    startup: list[Task] = field(default_factory=list)
    shutdown: list[Task] = field(default_factory=list)
    sources: list[tuple[str, Provider]] = field(default_factory=list)
    edition: str | None = None

    def merge(self, other: Registry) -> None:
        self.loaded += other.loaded
        self.routers += other.routers
        self.template_dirs += other.template_dirs
        self.static.update(other.static)
        self.tabs += other.tabs
        self.tabs.sort(key=lambda t: (t.order, t.id))
        self.migration_dirs += other.migration_dirs
        self.startup += other.startup
        self.shutdown += other.shutdown
        self.sources += other.sources
        if other.edition:
            self.edition = other.edition


class Hooks:
    """What ``register(app, hooks)`` receives. Every method records; ``create_app`` applies."""

    def __init__(self, name: str, registry: Registry) -> None:
        self.name = name
        self._reg = registry

    def router(self, router: APIRouter) -> None:
        """Include an ``APIRouter`` (under its own prefix; ``Authenticated`` is available to it)."""
        self._reg.routers.append(router)

    def templates(self, directory: str | Path) -> None:
        """A Jinja templates directory, searched after the app's own."""
        self._reg.template_dirs.append(_dir(directory, "templates"))

    def static(self, name: str, directory: str | Path) -> None:
        """Files served under ``/static/ext/<name>/``."""
        if not _NAME.match(name):
            raise ValueError(f"static name {name!r}: lowercase letters, digits, - or _")
        self._reg.static[name] = _dir(directory, "static")

    def tab(
        self,
        id: str,  # noqa: A002 — the tab's id in the DOM
        label: str,
        template: str,
        script: str | None = None,
        style: str | None = None,
        order: int = 100,
        icon: str = "puzzle",
    ) -> None:
        """A settings tab: ``template`` is the panel's fragment (resolved through the templates
        this extension added); ``script`` and ``style`` are files under its static directory,
        loaded by the settings page. ``icon`` names a symbol in the chrome's sprite. On a desk
        the tab follows the built-in ones; on a phone it sits behind *More*."""
        if not _NAME.match(id) or id in BUILTIN_TABS:
            raise ValueError(f"tab id {id!r}: lowercase, not one of {BUILTIN_TABS}")
        if any(t.id == id for t in self._reg.tabs):
            raise ValueError(f"tab id {id!r} registered twice")
        self._reg.tabs.append(Tab(id, label, template, self.name, script, style, order, icon))

    def migrations(self, directory: str | Path) -> None:
        """An Alembic version location: its revisions migrate with the core's at boot."""
        self._reg.migration_dirs.append(_dir(directory, "migrations"))

    def on_startup(self, task: Task) -> None:
        """``async def task(app)`` run inside the lifespan after the database is up."""
        self._reg.startup.append(task)

    def on_shutdown(self, task: Task) -> None:
        """``async def task(app)`` run before the database is disposed."""
        self._reg.shutdown.append(task)

    def board_source(self, provider: Provider) -> None:
        """``provider(session, at, display) -> BoardSource | None``: asked by ``/api/board/current``
        before the rotation. Rows it returns show with their own slot; ``None`` means the rotation
        runs as usual. Providers are asked in registration order; the first answer wins."""
        self._reg.sources.append((self.name, provider))

    def edition(self, name: str) -> None:
        """Name the edition this build is (the footer, ``/api/health``)."""
        self._reg.edition = name.strip() or self._reg.edition


def _dir(directory: str | Path, what: str) -> Path:
    p = Path(directory).resolve()
    if not p.is_dir():
        raise FileNotFoundError(f"{what} directory {p} does not exist")
    return p


def load_extensions(app: FastAPI) -> Registry:
    """Find and register every extension; a failing one is logged and leaves nothing behind."""
    registry = Registry()
    for ep in sorted(entry_points(group=GROUP), key=lambda e: e.name):
        staged = Registry()
        try:
            register = ep.load()
            register(app, Hooks(ep.name, staged))
        except Exception:  # noqa: BLE001 — one extension never stops the board
            log.exception("extension %r failed to load and is skipped", ep.name)
            continue
        staged.loaded.append(Loaded(ep.name, _version(ep)))
        registry.merge(staged)
        log.info("extension %s %s loaded", ep.name, staged.loaded[0].version)
    app.state.ext = registry
    app.state.extensions = [{"name": x.name, "version": x.version} for x in registry.loaded]
    return registry


def ask_sources(
    sources: list[tuple[str, Provider]], session: Session, at: datetime, display: Mapping[str, Any]
) -> BoardSource | None:
    """The first board source with text wins the board; the quickest poll hint of all that
    answered rides along. Standby hints alone give ``BoardSource(None, poll=…)``. One that raises
    is logged and skipped this poll."""
    hints: list[int] = []
    for name, provider in sources:
        try:
            found = provider(session, at, display)
        except Exception:  # noqa: BLE001 — a source never takes the board down
            log.exception("board source of %r failed and is skipped for this poll", name)
            continue
        if found is None:
            continue
        if found.poll:
            hints.append(found.poll)
        if found.text is not None:
            quickest = min(hints) if hints else None
            return found if found.poll == quickest else replace(found, poll=quickest)
    if hints:
        return BoardSource(None, poll=min(hints))
    return None


def _version(ep) -> str:
    dist = getattr(ep, "dist", None)
    return str(getattr(dist, "version", "") or "")
