"""Extension points (#156) and the edition (#157): a fixture package plugs in through every hook; a
broken one is skipped; with none installed the page and the API are what they were."""

import logging
import re
import sqlite3
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import __version__, extensions
from app.extensions import Hooks, Registry
from app.main import create_app
from tests import ext_fixture

SIX = ["board", "messages", "pictures", "guests", "boards", "setup"]


@pytest.fixture(autouse=True)
def _quiet_caption():
    """The fixture's board source starts and ends silent."""
    ext_fixture.CAPTION.update(text=None, seconds=None, remaining=None, poll=None)
    ext_fixture.CAPTION["raise"] = False
    yield
    ext_fixture.CAPTION.update(text=None, seconds=None, remaining=None, poll=None)
    ext_fixture.CAPTION["raise"] = False


def entry(name, register, version="0.1.0"):
    """What importlib.metadata hands back: a name, load(), the distribution's version."""
    return SimpleNamespace(name=name, load=lambda: register, dist=SimpleNamespace(version=version))


def installed(monkeypatch, *entries):
    monkeypatch.setattr(extensions, "entry_points", lambda group: list(entries))


def panels(html):
    return re.findall(r'<div id="panel-([a-z]+)" class="panel"', html)


def test_an_extension_plugs_in_through_every_hook(settings, monkeypatch):
    installed(monkeypatch, entry("hello", ext_fixture.register))
    with TestClient(create_app(settings)) as c:
        token = c.app.state.api_token
        auth = {"Authorization": f"Bearer {token}"}
        # the router, under its own prefix, with the core's auth available to it
        assert c.get("/api/hello").json() == {"hello": "world"}
        assert c.get("/api/hello/private").status_code == 401
        assert c.get("/api/hello/private", headers=auth).json() == {"ok": True}
        # the static directory, mounted before /static
        css = c.get("/static/ext/hello/hello.css")
        assert css.status_code == 200 and "dashed" in css.text
        # the tab: a button in the bar, a panel from the extension's template, its script, and
        # More for the phone with a Back row on the panel
        html = c.get("/settings", headers=auth).text
        assert 'id="tab-hello" aria-controls="panel-hello"' in html
        assert panels(html) == [*SIX, "hello", "more"]
        assert "HELLO-FIXTURE-PANEL" in html
        assert '<script src="/static/ext/hello/hello.js" defer></script>' in html
        assert '<link rel="stylesheet" href="/static/ext/hello/hello.css">' in html
        assert html.index("hello.css") < html.index("<body"), "its stylesheet loads in the head"
        assert 'id="tab-more" aria-controls="panel-more"' in html
        assert 'data-tab="hello"' in html and 'data-tab="more"' in html
        assert html.index('id="panel-hello"') > html.index('id="panel-setup"')
        assert html.index('id="panel-more"') < html.index('<aside id="side"')
        # the edition the extension named: the footer and the API
        assert '<span id="edition">TEST edition</span>' in html
        assert c.get("/api/health").json() == {
            "ok": True,
            "version": __version__,
            "edition": "TEST",
            "extensions": [{"name": "hello", "version": "0.1.0"}],
        }
        # the startup task ran after the database came up
        assert c.app.state.hello_started is True
        assert not hasattr(c.app.state, "hello_stopped")
        # the migration: a second Alembic base, upgraded with the core's
        db = sqlite3.connect(settings.data_dir / "departureboard.db")
        assert db.execute("SELECT count(*) FROM ext_hello").fetchone() == (0,)
        heads = {r[0] for r in db.execute("SELECT version_num FROM alembic_version")}
        assert heads == {"0003", "ext_hello_0001"}
        db.close()
    assert c.app.state.hello_stopped is True


def test_a_broken_extension_is_logged_and_skipped(settings, monkeypatch, caplog):
    installed(
        monkeypatch,
        entry("zz-broken", ext_fixture.register_broken),
        entry("hello", ext_fixture.register),
    )
    with caplog.at_level(logging.ERROR, logger="departureboard.extensions"):
        with TestClient(create_app(settings)) as c:
            auth = {"Authorization": f"Bearer {c.app.state.api_token}"}
            assert c.get("/api/health").json()["extensions"] == [
                {"name": "hello", "version": "0.1.0"}
            ]
            html = c.get("/settings", headers=auth).text
            assert "tab-broken" not in html, "half a registration leaves nothing behind"
            assert 'id="tab-hello"' in html
    assert "zz-broken" in caplog.text and "skipped" in caplog.text


def test_without_an_extension_nothing_changes(client, token):
    assert client.get("/api/health").json() == {
        "ok": True,
        "version": __version__,
        "edition": "community",
        "extensions": [],
    }
    html = client.get("/settings", headers={"Authorization": f"Bearer {token}"}).text
    assert panels(html) == SIX
    for marker in ("tab-more", 'class="ext"', "data-ext=", "data-tab=", "/static/ext/"):
        assert marker not in html, marker
    assert client.app.state.ext.tabs == [] and client.app.state.extensions == []
    assert client.get("/static/ext/hello/hello.css").status_code == 404
    board = client.get("/api/board/current").json()
    assert set(board) == {"stamp", "message_id", "rows", "settings", "timer"}, "no poll key"


def test_a_board_source_takes_the_board_for_a_moment_without_a_message(
    settings, monkeypatch, caplog
):
    """#185: the provider is asked before the rotation; rows, slot and the poll hint on the wire;
    the ETag follows the text; nothing written to messages; None → the rotation; raise → skipped."""
    installed(monkeypatch, entry("hello", ext_fixture.register))
    cap = ext_fixture.CAPTION
    with TestClient(create_app(settings)) as c:
        auth = {"Authorization": f"Bearer {c.app.state.api_token}"}
        c.post("/api/messages", json={"text": "SCHEDULED"}, headers=auth)
        r = c.get("/api/board/current")
        assert r.json()["rows"][0][:9] == list("SCHEDULED") and "poll" not in r.json()
        etag = r.headers["ETag"]

        cap.update(text="HELLO THERE", seconds=10, remaining=7, poll=1)
        r = c.get("/api/board/current", headers={"If-None-Match": etag})
        assert r.status_code == 200, "the source changes the stamp"
        j = r.json()
        assert j["rows"][0][:11] == list("HELLO THERE")
        assert j["message_id"] is None
        assert j["timer"] == {"seconds": 10, "remaining": 7, "own": True}
        assert j["poll"] == 1
        etag2 = r.headers["ETag"]
        assert etag2 != etag

        cap.update(text="HELLO AGAIN")
        r = c.get("/api/board/current", headers={"If-None-Match": etag2})
        assert r.status_code == 200 and r.json()["rows"][0][:11] == list("HELLO AGAIN")
        assert len(c.get("/api/messages", headers=auth).json()) == 1, "no message written"

        cap.update(text="NO SLOT", seconds=None, remaining=None, poll=None)
        j = c.get("/api/board/current").json()
        assert j["rows"][0][:7] == list("NO SLOT") and j["timer"] is None and "poll" not in j

        cap.update(text=None)
        j = c.get("/api/board/current").json()
        assert j["rows"][0][:9] == list("SCHEDULED") and "poll" not in j, "None → the rotation"

        cap["raise"] = True
        with caplog.at_level(logging.ERROR, logger="departureboard.extensions"):
            j = c.get("/api/board/current").json()
        assert j["rows"][0][:9] == list("SCHEDULED"), "a failing source is skipped"
        assert "skipped for this poll" in caplog.text


def test_the_footer_names_the_build(client, token):
    html = client.get("/settings", headers={"Authorization": f"Bearer {token}"}).text
    foot = html[
        html.index('<footer class="edition">') : html.index(
            "</footer>", html.index('<footer class="edition">')
        )
    ]
    assert f"DepartureBoard {__version__}" in foot
    assert '<span id="edition">Community edition</span>' in foot
    assert "GPL-3.0-or-later" in foot
    assert 'href="https://github.com/cmldexter/DepartureBoard"' in foot
    assert "@feltbykraft" in foot, "the credit stays"
    assert html.index('<footer class="edition">') > html.index('<dialog id="sheet"')


def test_hooks_refuse_what_would_break_the_page(tmp_path):
    hooks = Hooks("x", Registry())
    for bad in ("Board", "board", "more", "has space", ""):
        with pytest.raises(ValueError):
            hooks.tab(bad, "Bad", "bad.html")
    hooks.tab("fine", "Fine", "fine.html")
    with pytest.raises(ValueError, match="twice"):
        hooks.tab("fine", "Again", "fine.html")
    with pytest.raises(FileNotFoundError):
        hooks.templates(tmp_path / "missing")
    with pytest.raises(ValueError):
        hooks.static("Bad Name", tmp_path)
    hooks.edition("  ")
    assert hooks._reg.edition is None, "a blank edition name is ignored"
