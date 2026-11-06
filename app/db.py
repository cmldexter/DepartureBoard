"""SQLite via SQLAlchemy 2, migrated by Alembic at startup."""

import os
from collections.abc import Iterable, Iterator
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import Settings

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


class Base(DeclarativeBase):
    pass


def make_engine(settings: Settings) -> Engine:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


def migrate(settings: Settings, extra_versions: Iterable[Path] = ()) -> None:
    """Bring the database to the latest Alembic revision (creates it on first boot).

    ``extra_versions`` are the version locations extensions bring (app/extensions.py): each is a
    base of its own, so every head is upgraded; with none, this is the core's single head."""
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    cfg = Config()
    cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    extra = [str(p) for p in extra_versions]
    if extra:
        cfg.set_main_option("path_separator", "os")
        cfg.set_main_option(
            "version_locations", os.pathsep.join([str(MIGRATIONS_DIR / "versions"), *extra])
        )
    command.upgrade(cfg, "heads")


class Database:
    def __init__(self, settings: Settings) -> None:
        self.engine = make_engine(settings)
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)

    def session(self) -> Iterator[Session]:
        with self.session_factory() as session:
            yield session
