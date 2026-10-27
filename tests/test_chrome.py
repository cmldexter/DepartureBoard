"""The chrome: the Lucide sprite, the macro's names, no emoji left in the tab bar or the HUD (#161, #162)."""

import re
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
SPRITE = APP / "static" / "icons" / "lucide.svg"
SVG = "{http://www.w3.org/2000/svg}"
VENDORED_AHEAD: set[str] = set()  # every symbol is used since S2 took monitor/sun/moon


def sprite_symbols() -> dict[str, ET.Element]:
    root = ET.parse(SPRITE).getroot()
    return {s.get("id").removeprefix("lucide-"): s for s in root.iter(f"{SVG}symbol")}


def names_used() -> set[str]:
    names: set[str] = set()
    for path in [*(APP / "templates").glob("*.html"), *(APP / "static" / "js").glob("*.js")]:
        text = path.read_text(encoding="utf-8")
        names |= set(re.findall(r'\bicon\("([a-z0-9-]+)"', text))
        names |= set(re.findall(r'\bico\("([a-z0-9-]+)"', text))
        names |= set(re.findall(r"#lucide-([a-z0-9-]+)", text))
    return names


def test_the_sprite_is_stroke_only_lucide():
    root = ET.parse(SPRITE).getroot()
    assert re.fullmatch(r"\d+\.\d+\.\d+", root.get("data-lucide") or "")
    assert root.get("hidden") == "hidden" and root.get("aria-hidden") == "true"
    # `hidden` alone does not hide an <svg>: the board page's body grid would stack it over the frame
    assert root.get("style") == "display:none"
    symbols = sprite_symbols()
    assert len(symbols) >= 20
    for name, s in symbols.items():
        assert s.get("viewBox") == "0 0 24 24", name
        assert s.get("stroke") == "currentColor" and s.get("fill") == "none", name
        assert s.get("stroke-width") == "2", name
        for el in s.iter():
            assert el.get("fill") in (None, "none"), (
                f"{name}: a filled shape would ignore the page's colour"
            )
            assert el.tag != f"{SVG}style", name
    assert "ISC" in (SPRITE.parent / "LICENSE-lucide.txt").read_text(encoding="utf-8")


def test_every_icon_the_chrome_uses_is_in_the_sprite_and_the_other_way_round():
    used = names_used()
    symbols = set(sprite_symbols())
    assert used - symbols == set(), "a template or script names an icon the sprite lacks"
    assert symbols - used == VENDORED_AHEAD, (
        "a symbol nothing uses — drop it from scripts/lucide-sprite.py"
    )


def test_third_party_names_the_vendored_version():
    version = ET.parse(SPRITE).getroot().get("data-lucide")
    third = (ROOT / "THIRD_PARTY.md").read_text(encoding="utf-8")
    assert f"Lucide {version}" in third
    script = (ROOT / "scripts" / "lucide-sprite.py").read_text(encoding="utf-8")
    assert f'VERSION = "{version}"' in script


def test_no_emoji_or_text_glyph_is_left_in_the_chrome():
    settings = (APP / "templates" / "settings.html").read_text(encoding="utf-8")
    board = (APP / "templates" / "board.html").read_text(encoding="utf-8")
    tabs = re.findall(r'<button type="button" role="tab".*?</button>', settings)
    assert len(tabs) == 6
    for tab in tabs:
        assert 'icon("' in tab
        assert not re.search(r"[\U0001F000-\U0001FAFF☀-➿]", tab), tab
    rows = re.findall(r'<button type="button" data-sheet=.*?</button>', settings)
    assert rows and all('icon("chevron-right")' in r and "›" not in r for r in rows)
    assert "⋯" not in settings and "‹" not in settings
    hud = re.findall(r'<(?:a|button)[^>]*class="hud"[^>]*>.*?</(?:a|button)>', board)
    assert len(hud) == 3
    for h in hud:
        assert 'icon("' in h and "⚙" not in h and "⛶" not in h, h


def test_every_page_prints_the_sprite_once(client, token):
    login = client.get("/settings").text  # signed out: the sign-in page
    assert "wordmark" in login and login.count('data-lucide="') == 1
    client.post("/settings/login", data={"token": token}, follow_redirects=False)
    for path in ("/", "/settings", "/integrate"):
        html = client.get(path).text
        assert html.count('data-lucide="') == 1, path
        assert html.count("<symbol ") >= 20, path
    guest = client.post("/api/guest/rotate", headers={"Authorization": f"Bearer {token}"}).json()
    assert (
        'data-lucide="' not in client.get(f"/guest/{guest['token']}").text
    )  # no icon, no "settings"
    html = client.get("/settings").text
    assert html.count('<use href="#lucide-') >= 20
    assert "wordmark" in html and 'icon-192.png" alt="" width="40"' in html


def test_base_css_keeps_every_colour_in_a_token():
    """Light and dark only change values: no raw colour outside the token blocks (#163)."""
    css = (APP / "static" / "css" / "base.css").read_text(encoding="utf-8")
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    blocks = re.findall(r"(?::root \{|\.page \{\n)[^}]*\}", css)
    rest = css
    for b in blocks:
        rest = rest.replace(b, "")
    raw = re.findall(r"#[0-9a-fA-F]{3,8}\b|rgba?\(", rest)
    assert raw == [], f"raw colours outside the tokens: {raw[:8]}"
    dark = re.search(r":root \{(.*?)\}", css, re.S).group(1)
    light = re.search(r':root\[data-theme="light"\] \.page \{(.*?)\}', css, re.S).group(1)
    system_light = re.search(
        r':root:not\(\[data-theme="dark"\]\) \.page \{(.*?)\}', css, re.S
    ).group(1)
    assert light.strip() == system_light.strip(), "the two light blocks carry the same values"
    for token in (
        "--bg",
        "--fg",
        "--muted",
        "--accent",
        "--surface",
        "--surface-2",
        "--border",
        "--rule",
        "--danger",
        "--input-bg",
        "--wordmark-a",
        "--scrim",
    ):
        assert f"{token}:" in dark and f"{token}:" in light, token
    for constant in ("--accent-fill", "--accent-ink", "--white", "--well", "--ok:"):
        assert constant in dark and constant not in light, f"{constant} is the same in both schemes"
    assert "color-scheme: light" in light and ".page { color-scheme: dark; }" in css


def test_appearance_is_a_device_preference_not_a_setting(client, token):
    """R3: the switch lives in localStorage + data-theme; /api/settings never learns it."""
    client.post("/settings/login", data={"token": token}, follow_redirects=False)
    assert (
        "appearance"
        not in client.get("/api/settings", headers={"Authorization": f"Bearer {token}"}).json()
    )
    html = client.get("/settings").text
    assert html.count('name="appearance"') == 3 and 'id="appearance"' in html
    base = (APP / "templates" / "base.html").read_text(encoding="utf-8")
    assert 'localStorage.getItem("departureboard.appearance")' in base
    assert base.index("departureboard.appearance") < base.index("base.css"), (
        "applied before the stylesheet"
    )
    board = client.get("/").text
    assert 'class="board-page' in board and 'class="page' not in board, (
        "the board page is never .page"
    )


def test_the_saves_take_the_busy_state():
    js = (APP / "static" / "js" / "settings.js").read_text(encoding="utf-8")
    assert js.count("busy(") >= 16
    assert "aria-busy" in js and "#lucide-loader-circle" in js
    css = (APP / "static" / "css" / "base.css").read_text(encoding="utf-8")
    for kind in (
        "button.secondary",
        "button.quiet",
        "button.danger",
        'button[aria-busy="true"]',
        ".icon.spin",
    ):
        assert kind in css, kind
    assert "max(44px, 2.75rem)" in css
