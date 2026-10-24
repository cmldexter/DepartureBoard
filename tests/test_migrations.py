"""A database made by an earlier release upgrades in place: rows read back, new columns null."""

import sqlite3

from alembic import command
from alembic.config import Config

from app.config import Settings
from app.db import MIGRATIONS_DIR
from app.main import create_app


def test_upgrade_from_baseline_keeps_rows(tmp_path):
    settings = Settings(data_dir=tmp_path / "data", api_token=None, _env_file=None)
    settings.data_dir.mkdir(parents=True)
    cfg = Config()
    cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(cfg, "0001")  # a v0.2.0 database
    db = sqlite3.connect(settings.data_dir / "departureboard.db")
    db.execute(
        "INSERT INTO messages (text, enabled, priority, repeat, repeat_days, source) VALUES (?, 1, 0, 'none', 0, 'ui')",
        ("OLD ROW",),
    )
    db.commit()
    db.close()

    with __import__("fastapi.testclient").testclient.TestClient(create_app(settings)) as client:
        token = client.app.state.api_token
        rows = client.get("/api/messages", headers={"Authorization": f"Bearer {token}"}).json()
    assert [(r["text"], r["show_seconds"]) for r in rows] == [("OLD ROW", None)]
    db = sqlite3.connect(settings.data_dir / "departureboard.db")
    assert db.execute("SELECT version_num FROM alembic_version").fetchone() == ("0002",)
    db.close()
