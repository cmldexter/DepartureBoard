"""Display settings: defaults, presets, bounds, and what the board page embeds."""

import json
import re

import pytest

from app.models import Setting
from app.services.display import display_settings, resolve_display

GRID_KEYS = ("rows", "cols", "animation", "demo")


def _config(html: str) -> dict:
    m = re.search(r'<script id="board-config" type="application/json">(.*?)</script>', html, re.S)
    assert m, "the board page embeds its config"
    return json.loads(m.group(1))


def _grid(html: str) -> dict:
    """The grid-related part of the config (the rest is theme and sound)."""
    c = _config(html)
    return {k: c[k] for k in GRID_KEYS}


def _cells(html: str) -> int:
    return len(re.findall(r'<div class="cell"', html))


def test_defaults_are_compact():
    d = resolve_display({})
    assert (d["grid_preset"], d["rows"], d["cols"]) == ("compact", 6, 22)
    assert d["animation"] == 60
    assert d["sound_enabled"] is True
    assert d["sound_volume"] == 0.6
    assert d["theme"] == "classic-black"


def test_large_preset():
    d = resolve_display({"grid_preset": "large", "rows": "4", "cols": "16"})
    assert (d["rows"], d["cols"]) == (8, 28), "a known preset wins over rows/cols"


@pytest.mark.parametrize(
    ("rows", "cols", "expected"),
    [("7", "30", (7, 30)), ("1", "99", (4, 36)), ("99", "1", (10, 16)), ("x", "", (6, 22))],
)
def test_custom_within_bounds(rows, cols, expected):
    d = resolve_display({"grid_preset": "custom", "rows": rows, "cols": cols})
    assert d["grid_preset"] == "custom"
    assert (d["rows"], d["cols"]) == expected


@pytest.mark.parametrize(("raw", "expected"), [("0", 0), ("100", 100), ("250", 100), ("-5", 0)])
def test_animation_bounds(raw, expected):
    assert resolve_display({"animation": raw})["animation"] == expected


def test_display_settings_reads_the_table(client):
    with next(client.app.state.db.session()) as session:
        session.add(Setting(key="grid_preset", value="large"))
        session.add(Setting(key="animation", value="0"))
        session.commit()
        d = display_settings(session)
    assert (d["rows"], d["cols"], d["animation"]) == (8, 28, 0)
    html = client.get("/").text
    assert _grid(html) == {"rows": 8, "cols": 28, "animation": 0, "demo": False}
    assert _cells(html) == 8 * 28


def test_board_page_embeds_defaults(client):
    html = client.get("/").text
    assert _grid(html) == {"rows": 6, "cols": 22, "animation": 60, "demo": False}


def test_demo_overrides_only_in_demo_mode(client):
    assert _config(client.get("/?preset=large&animation=0").text)["rows"] == 6
    c = _grid(client.get("/?demo&preset=large&animation=0").text)
    assert c == {"rows": 8, "cols": 28, "animation": 0, "demo": True}
    c = _config(client.get("/?demo&rows=10&cols=36").text)
    assert (c["rows"], c["cols"]) == (10, 36)
    c = _config(client.get("/?demo&rows=99").text)
    assert (c["rows"], c["cols"]) == (10, 22), "rows alone makes it custom, clamped"


def test_board_page_theme_and_sound(client):
    html = client.get("/").text
    assert "/static/themes/classic-black.css" in html
    assert "/static/fonts/fonts.css" in html
    assert 'id="fullscreen"' in html and 'id="keep-awake"' in html
    c = _config(html)
    assert (c["theme"], c["sound_enabled"], c["sound_volume"]) == ("classic-black", True, 0.6)
    with next(client.app.state.db.session()) as session:
        session.add(Setting(key="theme", value="walnut"))
        session.add(Setting(key="sound_enabled", value="false"))
        session.commit()
    html = client.get("/").text
    assert "/static/themes/walnut.css" in html
    assert _config(html)["sound_enabled"] is False
    assert "/static/themes/midnight.css" in client.get("/?demo&theme=midnight").text
    assert "/static/themes/walnut.css" in client.get("/?theme=midnight").text, (
        "no override outside demo"
    )
    assert "/static/themes/classic-black.css" in client.get("/?demo&theme=nope").text, (
        "unknown → default"
    )


def test_theme_assets_exist(client):
    from app.models import THEMES

    for t in THEMES:
        assert client.get(f"/static/themes/{t}.css").status_code == 200, t
    for f in ("oswald", "jetbrains-mono", "nunito"):
        assert client.get(f"/static/fonts/{f}.woff2").status_code == 200, f
    for v in ("keep-awake.mp4", "keep-awake.webm"):
        assert client.get(f"/static/video/{v}").status_code == 200, v
