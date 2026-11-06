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
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from importlib.metadata import entry_points
from pathlib import Path

from fastapi import APIRouter, FastAPI

GROUP = "departureboard.extensions"
BUILTIN_TABS = ("board", "messages", "pictures", "guests", "boards", "setup", "more")
_NAME = re.compile(r"^[a-z][a-z0-9_-]*$")
log = logging.getLogger("departureboard.extensions")

Task = Callable[[FastAPI], Awaitable[None]]


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


def _version(ep) -> str:
    dist = getattr(ep, "dist", None)
    return str(getattr(dist, "version", "") or "")
