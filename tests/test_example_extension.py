"""The example extension (#158) loads through its own entry point and does what the doc says — so
the doc, the example and the hooks cannot drift apart. Not installed: registered the way the
fixture is, from the path `pyproject.toml` names."""

import importlib
import sqlite3
import sys
import tomllib
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app import extensions
from app.main import create_app

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "extension-hello"


def load_example():
    """(name, register, version) from the example's pyproject, the way importlib would."""
    meta = tomllib.loads((EXAMPLE / "pyproject.toml").read_text())
    ((name, target),) = meta["project"]["entry-points"]["departureboard.extensions"].items()
    module, attr = target.split(":")
    if str(EXAMPLE) not in sys.path:
        sys.path.insert(0, str(EXAMPLE))
    return name, getattr(importlib.import_module(module), attr), meta["project"]["version"]


def test_the_example_extension_installs_and_renders(settings, monkeypatch):
    name, register, version = load_example()
    monkeypatch.setattr(
        extensions,
        "entry_points",
        lambda group: [
            SimpleNamespace(name=name, load=lambda: register, dist=SimpleNamespace(version=version))
        ],
    )
    with TestClient(create_app(settings)) as c:
        token = c.app.state.api_token
        auth = {"Authorization": f"Bearer {token}"}
        assert c.get("/api/health").json()["extensions"] == [{"name": "hello", "version": version}]
        # the tab, its panel from the example's template, its script and stylesheet
        html = c.get("/settings", headers=auth).text
        assert 'id="tab-hello" aria-controls="panel-hello"' in html
        assert 'id="hello-form" class="sheet-block"' in html and 'data-sheet="hello-form"' in html
        assert '<script src="/static/ext/hello/hello.js" defer></script>' in html
        assert '<link rel="stylesheet" href="/static/ext/hello/hello.css">' in html
        assert c.get("/static/ext/hello/hello.js").status_code == 200
        assert c.get("/static/ext/hello/hello.css").status_code == 200
        # the router: behind the token, one key of its own, not in the core's settings
        assert c.get("/api/hello").status_code == 401
        assert c.get("/api/hello", headers=auth).json() == {"greeting": "HELLO"}
        r = c.put("/api/hello", json={"greeting": "GOOD MORNING"}, headers=auth)
        assert r.status_code == 200 and r.json() == {"greeting": "GOOD MORNING"}
        assert c.get("/api/hello", headers=auth).json() == {"greeting": "GOOD MORNING"}
        assert c.put("/api/hello", json={"greeting": ""}, headers=auth).status_code == 422
        assert "hello.greeting" not in c.get("/api/settings", headers=auth).json()
        db = sqlite3.connect(settings.data_dir / "departureboard.db")
        assert db.execute("SELECT value FROM settings WHERE key='hello.greeting'").fetchone() == (
            "GOOD MORNING",
        )
        db.close()
        # the example's routes are in the OpenAPI under its tag
        paths = c.get("/openapi.json").json()["paths"]
        assert set(paths["/api/hello"]) == {"get", "put"}
        assert paths["/api/hello"]["get"]["tags"] == ["hello"]
    # the doc names the example and the example names the doc
    assert "examples/extension-hello/" in (ROOT / "docs" / "extensions.md").read_text()
    assert "docs/extensions.md" in (EXAMPLE / "README.md").read_text()
