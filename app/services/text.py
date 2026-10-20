"""Message text → board cells.

A message is typed as text. The board shows cells: a character from the flap set, a colour chip
`{red}`, an uploaded image `{img:slug}`, or an emoji. Rows split on newlines; a row longer than
the board word-wraps. Capacity is rows × cols cells, a token counting as one cell. Characters
outside the flap set are uppercased and stripped of accents; what is still unknown becomes a
blank and is reported, so the organizer can warn before the board shows a hole.

The flap set lives in one JSON file, app/static/flapset.json, which the board script mirrors.
"""

import json
import re
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

FLAPSET_PATH = Path(__file__).resolve().parent.parent / "static" / "flapset.json"

# A cell is a one-character string from the flap set, or a token dict:
#   {"chip": "red"} · {"img": "slug"} · {"emoji": "🎉"}
Cell = str | dict[str, str]

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
_TOKEN_RE = re.compile(r"\{(?P<body>[a-z]+(?::[a-z0-9-]+)?)\}")

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

    @property
    def overflow(self) -> bool:
        return len(self.rows) > self.grid_rows

    grid_rows: int = 0
    grid_cols: int = 0


def tokenize(line: str) -> tuple[list[Cell], list[str], list[str]]:
    """One line of text → cells; also the characters it could not show and the image slugs."""
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
            if body.startswith("img:") and SLUG_RE.match(body[4:]):
                cells.append({"img": body[4:]})
                images.append(body[4:])
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


def _wrap(cells: list[Cell], cols: int) -> list[list[Cell]]:
    """Word-wrap a row of cells to `cols`; a word longer than the row is cut."""
    if len(cells) <= cols:
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
        while len(word) > cols:
            if line:
                rows.append(line)
                line = []
            rows.append(word[:cols])
            word = word[cols:]
        if not word:
            continue
        if line and len(line) + 1 + len(word) > cols:
            rows.append(line)
            line = list(word)
        elif line:
            line = line + [" "] + word
        else:
            line = list(word)
    if line or not rows:
        rows.append(line)
    return rows


def layout(text: str, rows: int, cols: int) -> Layout:
    """Lay `text` out on a rows × cols board. Rows split on newlines, then word-wrap."""
    out = Layout(rows=[], capacity=rows * cols, grid_rows=rows, grid_cols=cols)
    for line in text.replace("\r\n", "\n").split("\n"):
        cells, unknown, images = tokenize(line.rstrip())
        out.unknown.extend(unknown)
        out.images.extend(images)
        for wrapped in _wrap(cells, cols):
            out.rows.append(wrapped)
    while out.rows and not out.rows[-1]:
        out.rows.pop()
    if not out.rows:
        out.rows = [[]]
    out.used = sum(len(r) for r in out.rows)
    return out


def padded_rows(lay: Layout) -> list[list[Cell]]:
    """The layout as exactly grid_rows rows of grid_cols cells, blanks filled in."""
    rows = [list(r) + [" "] * (lay.grid_cols - len(r)) for r in lay.rows[: lay.grid_rows]]
    while len(rows) < lay.grid_rows:
        rows.append([" "] * lay.grid_cols)
    return rows


def capacity_error(lay: Layout) -> str | None:
    """A readable reason the text does not fit, or None."""
    if lay.overflow:
        return (
            f"The message needs {len(lay.rows)} rows but the board has {lay.grid_rows} "
            f"({lay.grid_cols} columns, {lay.capacity} cells)."
        )
    return None
