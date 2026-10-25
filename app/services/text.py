"""Message text → board cells.

A message is typed as text. The board shows cells: a character from the flap set, a colour chip
`{red}`, an uploaded image `{img:slug}`, or an emoji. Rows split on newlines; a row longer than
the board word-wraps. Capacity is rows × cols cells, a token counting as one cell — except a
picture, which takes the block of w × h cells set on the Images panel (or `{img:slug@6x2}`
inline): it is placed as a word of its own, never cut, and the rows beneath it are pushed down
with the block's parts in those columns. Every covered cell carries the whole block
(`{"img", "w", "h", "x", "y", "fit", "ar"}`) so the board can paint its slice. Characters
outside the flap set are uppercased and stripped of accents; what is still unknown becomes a
blank and is reported, so the organizer can warn before the board shows a hole.

The flap set lives in one JSON file, app/static/flapset.json, which the board script mirrors.
"""

import json
import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

FLAPSET_PATH = Path(__file__).resolve().parent.parent / "static" / "flapset.json"

# A cell is a one-character string from the flap set, or a token dict:
#   {"chip": "red"} · {"emoji": "🎉"} · {"img": "slug"} (one cell, stretched — a picture from
#   before sizes existed) · {"img": "slug", "w": 9, "h": 1, "x": 3, "y": 0, "fit": "contain",
#   "ar": 6.4} (one part of a block; "ar" only when the pixel size is known)
Cell = str | dict[str, Any]

# How a picture sits on the board: w × h cells, fit, pixel aspect — app.services.images.Size
Sizes = Mapping[str, Mapping[str, Any]]
MAX_W, MAX_H = 36, 10

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
_TOKEN_RE = re.compile(r"\{(?P<body>[a-z]+(?::[a-z0-9-]+(?:@(?P<w>\d{1,2})x(?P<h>\d{1,2}))?)?)\}")

# Emoji: a base pictograph plus the marks that may follow it (variation selector, skin tone,
# zero-width joiner sequences, keycap, flag pairs, tag sequences). Enough for the emoji people
# type; the board shows whatever the TV's font has.
_EMOJI_BASE = (
    "[\U0001f000-\U0001faff\U00002600-\U000027bf\U00002b00-\U00002bff\U0001f1e6-\U0001f1ff"
    "⌀-⏿←-⇿〰〽㊗㊙©®™ℹ]"
)
_EMOJI_MARK = "[️⃣\U0001f3fb-\U0001f3ff\U000e0020-\U000e007f]"
_EMOJI_RE = re.compile(
    rf"(?:[0-9#*]️?⃣)"  # keycaps 1️⃣
    rf"|(?:[\U0001F1E6-\U0001F1FF]{{2}})"  # flags 🇨🇭
    rf"|(?:{_EMOJI_BASE}{_EMOJI_MARK}*(?:‍{_EMOJI_BASE}{_EMOJI_MARK}*)*)"  # 👩‍💻, 👍🏽, ☀️
)


@lru_cache
def flapset() -> dict:
    return json.loads(FLAPSET_PATH.read_text())


@lru_cache
def charset() -> frozenset[str]:
    return frozenset(flapset()["sequence"])


@lru_cache
def chips() -> frozenset[str]:
    return frozenset(flapset()["chips"])


def normalize_char(ch: str) -> str | None:
    """The flap-set character for `ch`, or None when the set has nothing for it."""
    if ch in charset():
        return ch
    stripped = "".join(
        c for c in unicodedata.normalize("NFD", ch) if not unicodedata.combining(c)
    ).upper()
    if stripped in charset():
        return stripped
    if ch.isspace():
        return " "
    return None


@dataclass
class Layout:
    rows: list[list[Cell]]
    capacity: int
    used: int = 0
    unknown: list[str] = field(default_factory=list)
    images: list[str] = field(default_factory=list)
    too_big: list[str] = field(default_factory=list)  # pictures wider or taller than the board

    @property
    def overflow(self) -> bool:
        return len(self.rows) > self.grid_rows

    grid_rows: int = 0
    grid_cols: int = 0


def _block(slug: str, size: Mapping[str, Any] | None, w: str | None, h: str | None) -> Cell:
    """The anchor cell for a picture: bare for a legacy one-cell picture, else the whole block."""
    if size is None and w is None:
        return {"img": slug}
    cell: dict[str, Any] = {
        "img": slug,
        "w": int(size["w"]) if size else 1,
        "h": int(size["h"]) if size else 1,
        "fit": str(size["fit"]) if size else "contain",
    }
    if w is not None and h is not None:  # the inline override {img:slug@WxH}
        cell["w"] = min(MAX_W, max(1, int(w)))
        cell["h"] = min(MAX_H, max(1, int(h)))
    if size and size.get("ar"):
        cell["ar"] = round(float(size["ar"]), 3)
    if size and size.get("solid"):  # drawn whole over the block, the flaps beneath blank
        cell["solid"] = True
    if size and size.get("qr"):
        cell["qr"] = True
    if size and size.get("v"):  # a replaced file is a new picture to the TV
        cell["v"] = int(size["v"])
    return cell


def tokenize(line: str, sizes: Sizes | None = None) -> tuple[list[Cell], list[str], list[str]]:
    """One line of text → cells; also the characters it could not show and the image slugs.

    A picture is one anchor cell here carrying its block size; `layout` expands it.
    """
    cells: list[Cell] = []
    unknown: list[str] = []
    images: list[str] = []
    i = 0
    while i < len(line):
        m = _TOKEN_RE.match(line, i)
        if m:
            body = m.group("body")
            if body in chips():
                cells.append({"chip": body})
                i = m.end()
                continue
            if body.startswith("img:"):
                slug = body[4:].split("@")[0]
                if SLUG_RE.match(slug):
                    size = (sizes or {}).get(slug)
                    cells.append(_block(slug, size, m.group("w"), m.group("h")))
                    images.append(slug)
                    i = m.end()
                    continue
            # Not a token we know: show the braces as text (they are in the flap set? no → blank)
        e = _EMOJI_RE.match(line, i)
        if e:
            cells.append({"emoji": e.group(0)})
            i = e.end()
            continue
        ch = line[i]
        i += 1
        if unicodedata.combining(ch) or ch in "️‍":
            continue  # stray marks after something we already consumed
        mapped = normalize_char(ch)
        if mapped is None:
            unknown.append(ch)
            cells.append(" ")
        else:
            cells.append(mapped)
    return cells, unknown, images


def _is_block(c: Cell) -> bool:
    return isinstance(c, dict) and "w" in c


def _width(c: Cell) -> int:
    return int(c["w"]) if _is_block(c) else 1


def _height(c: Cell) -> int:
    return int(c["h"]) if _is_block(c) else 1


def _wlen(cells: list[Cell]) -> int:
    return sum(_width(c) for c in cells)


def _wrap(cells: list[Cell], cols: int) -> list[list[Cell]]:
    """Word-wrap a row of cells to `cols`, measuring pictures by their width.

    A word longer than the row is cut between cells, never through a block (a block is at most
    `cols` wide, see `layout`).
    """
    if _wlen(cells) <= cols:
        return [cells]
    rows: list[list[Cell]] = []
    words: list[list[Cell]] = [[]]
    for c in cells:
        if c == " ":
            words.append([])
        else:
            words[-1].append(c)
    line: list[Cell] = []
    for word in words:
        while _wlen(word) > cols:
            if line:
                rows.append(line)
                line = []
            k, acc = 0, 0
            while k < len(word) and acc + _width(word[k]) <= cols:
                acc += _width(word[k])
                k += 1
            rows.append(word[:k])
            word = word[k:]
        if not word:
            continue
        if line and _wlen(line) + 1 + _wlen(word) > cols:
            rows.append(line)
            line = list(word)
        elif line:
            line = line + [" "] + word
        else:
            line = list(word)
    if line or not rows:
        rows.append(line)
    return rows


def _part(block: dict[str, Any], x: int, y: int) -> Cell:
    return {**block, "x": x, "y": y}


def _expand(rows: list[list[Cell]]) -> list[list[Cell]]:
    """Blocks → their parts. A block takes `w` columns of its row and `h − 1` rows beneath it,
    which are inserted holding the block's lower parts (text below is pushed down)."""
    out: list[list[Cell]] = []
    for row in rows:
        extra = max((_height(c) for c in row), default=1) - 1
        below: list[list[Cell]] = [[] for _ in range(extra)]
        line: list[Cell] = []
        for c in row:
            if not _is_block(c):
                line.append(c)
                continue
            x0 = len(line)
            w, h = _width(c), _height(c)
            line.extend(_part(c, dx, 0) for dx in range(w))
            for dy in range(1, h):
                tail = below[dy - 1]
                tail.extend([" "] * (x0 - len(tail)))
                tail.extend(_part(c, dx, dy) for dx in range(w))
        out.append(line)
        out.extend(below)
    return out


def layout(text: str, rows: int, cols: int, sizes: Sizes | None = None) -> Layout:
    """Lay `text` out on a rows × cols board. Rows split on newlines, then word-wrap, then
    pictures expand into their blocks. `sizes` is `images.sizes(settings)`; without it every
    picture is one cell."""
    out = Layout(rows=[], capacity=rows * cols, grid_rows=rows, grid_cols=cols)
    wrapped_rows: list[list[Cell]] = []
    for line in text.replace("\r\n", "\n").split("\n"):
        cells, unknown, images = tokenize(line.rstrip(), sizes)
        out.unknown.extend(unknown)
        out.images.extend(images)
        for c in cells:
            if _is_block(c) and (c["w"] > cols or c["h"] > rows):
                out.too_big.append(
                    f"{{img:{c['img']}}} is {c['w']}×{c['h']} but the board has "
                    f"{cols} columns and {rows} rows"
                )
                c["w"], c["h"] = min(int(c["w"]), cols), min(int(c["h"]), rows)
        wrapped_rows.extend(_wrap(cells, cols))
    out.used = sum(_width(c) * _height(c) for r in wrapped_rows for c in r)
    out.rows = _expand(wrapped_rows)
    while out.rows and not out.rows[-1]:
        out.rows.pop()
    if not out.rows:
        out.rows = [[]]
    return out


def padded_rows(lay: Layout) -> list[list[Cell]]:
    """The layout as exactly grid_rows rows of grid_cols cells, blanks filled in."""
    rows = [list(r) + [" "] * (lay.grid_cols - len(r)) for r in lay.rows[: lay.grid_rows]]
    while len(rows) < lay.grid_rows:
        rows.append([" "] * lay.grid_cols)
    return rows


def capacity_error(lay: Layout) -> str | None:
    """A readable reason the text does not fit, or None."""
    if lay.too_big:
        return lay.too_big[0] + ". Make the picture smaller on the Images panel."
    if lay.overflow:
        return (
            f"The message needs {len(lay.rows)} rows but the board has {lay.grid_rows} "
            f"({lay.grid_cols} columns, {lay.capacity} cells)."
        )
    return None
