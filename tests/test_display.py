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


def _text(html: str) -> str:
    """The server-rendered glyphs, one per cell (each cell carries its glyph four times)."""
    return "".join(re.findall(r'<span class="glyph">(.*?)</span>', html)[::4])


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


CONFIG_KEYS = {
    "rows",
    "cols",
    "animation",
    "sound_enabled",
    "sound_volume",
    "theme",
    "poll_seconds",
    "demo",
    "embed",
    "preview",
}

HUD = (
    'id="cast"',
    "/static/js/cast.js",
    'id="settings-link"',
    'id="fullscreen"',
    'id="keep-awake"',
    'id="status"',
    'id="net"',
    "/static/js/wake.js",
    "/static/js/sound.js",
)


def test_board_config_keys(client):
    c = _config(client.get("/").text)
    assert set(c) == CONFIG_KEYS
    assert (c["embed"], c["preview"]) == (False, False)


def test_embed_page_has_no_hud(client):
    html = client.get("/?embed").text
    for needle in HUD:
        assert needle not in html, needle
    assert "/static/js/board.js" in html and "/static/js/flap.js" in html
    assert 'class="board-page embed"' in html
    assert _cells(html) == 6 * 22
    c = _config(html)
    assert (c["embed"], c["preview"], c["demo"]) == (True, False, False)
    assert "SET UP AT /SETTINGS" in _text(html), "the live frame still starts on the placeholder"


def test_preview_page_never_polls_or_demos(client):
    html = client.get("/?embed&preview&demo&preset=large").text
    c = _config(html)
    assert (c["embed"], c["preview"], c["demo"]) == (True, True, False)
    assert (c["rows"], c["cols"]) == (6, 22), "demo overrides do not apply in preview"
    assert _text(html).strip() == "", "a preview starts blank"
    assert _cells(html) == 6 * 22
    for needle in HUD:
        assert needle not in html, needle


def test_board_page_has_the_settings_link(client):
    html = client.get("/").text
    m = re.search(r'<a id="settings-link"[^>]*>', html)
    assert m, "⚙ opposite ⛶"
    tag = m.group(0)
    for needle in (
        'class="hud"',
        'href="/settings"',
        'target="_blank"',
        'rel="noopener"',
        "aria-label=",
    ):
        assert needle in tag, needle
    assert 'id="settings-link"' not in client.get("/?embed").text


def test_board_page_has_a_hidden_cast_button(client):
    html = client.get("/").text
    m = re.search(r'<button type="button" id="cast"[^>]*>', html)
    assert m, "the Cast button is in the HUD"
    assert "hidden" in m.group(0), "hidden until cast.js finds the API and https"
    assert "/static/js/cast.js" in html
    assert 'id="cast"' not in client.get("/?embed").text
