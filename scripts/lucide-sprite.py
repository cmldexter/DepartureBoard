#!/usr/bin/env python3
"""Vendor the Lucide icons the chrome uses into one SVG sprite.

    uv run python scripts/lucide-sprite.py            # the version pinned below
    uv run python scripts/lucide-sprite.py 1.62.0     # bump the pin

Writes app/static/icons/lucide.svg (one <symbol> per name, stroke-only, currentColor) and
app/static/icons/LICENSE-lucide.txt (Lucide's ISC text). Only the names in NAMES are vendored;
THIRD_PARTY.md names the version. Stdlib only.
"""

import re
import sys
import urllib.request
from pathlib import Path

VERSION = "1.61.0"

# What the chrome uses (tests/test_chrome.py asserts the set matches the templates and the JS).
NAMES = [
    # the six tabs
    "tv",
    "message-square",
    "image",
    "party-popper",
    "calendar-days",
    "settings",
    # menus and chevrons
    "ellipsis",
    "chevron-right",
    "chevron-left",
    # actions
    "copy",
    "cast",
    "maximize",
    "loader-circle",
    "plus",
    "upload",
    "qr-code",
    "camera",
    "trash-2",
    "pencil",
    "copy-plus",
    "power",
    "rotate-cw",
    "log-out",
    "x",
    # the appearance switch (Epic 27 S2)
    "monitor",
    "sun",
    "moon",
]

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "app" / "static" / "icons" / "lucide.svg"
LICENSE = ROOT / "app" / "static" / "icons" / "LICENSE-lucide.txt"
BASE = "https://unpkg.com/lucide-static@{v}/"


def fetch(url: str) -> str:
    with urllib.request.urlopen(url, timeout=30) as r:  # noqa: S310 — a pinned CDN URL
        return r.read().decode("utf-8")


def inner(svg: str, name: str) -> str:
    """The paths inside Lucide's <svg …>…</svg>, with the comment and the class dropped."""
    m = re.search(r"<svg[^>]*>(.*)</svg>", svg, re.S)
    if not m:
        raise SystemExit(f"{name}: not an svg")
    body = re.sub(r"<!--.*?-->", "", m.group(1), flags=re.S)
    return "\n".join("    " + line.strip() for line in body.strip().splitlines() if line.strip())


def main(version: str) -> None:
    base = BASE.format(v=version)
    symbols = []
    for name in NAMES:
        svg = fetch(f"{base}icons/{name}.svg")
        symbols.append(
            f'  <symbol id="lucide-{name}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">\n'
            f"{inner(svg, name)}\n  </symbol>"
        )
    sprite = (
        f'<svg xmlns="http://www.w3.org/2000/svg" data-lucide="{version}" '
        'hidden="hidden" aria-hidden="true" focusable="false" style="display:none">\n'
        # style, not only hidden: the hidden attribute does not hide an <svg> on the board page,
        # whose body grid would then stack the sprite above the frame
        + "\n".join(symbols)
        + "\n</svg>\n"
    )
    OUT.write_text(sprite, encoding="utf-8")
    LICENSE.write_text(fetch(f"{base}LICENSE"), encoding="utf-8")
    print(f"{OUT.relative_to(ROOT)}: {len(NAMES)} symbols from lucide-static {version}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else VERSION)
