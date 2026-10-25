"""Text → cells: the flap set, tokens, emoji, wrapping and capacity."""

import json
import re
from pathlib import Path

import pytest

from app.services.text import (
    FLAPSET_PATH,
    capacity_error,
    layout,
    normalize_char,
    padded_rows,
    tokenize,
)


def test_flapset_json_matches_flap_js():
    """R3: one character set. flap.js mirrors flapset.json; this keeps them from drifting."""
    data = json.loads(FLAPSET_PATH.read_text())
    js = (Path(__file__).resolve().parent.parent / "app/static/js/flap.js").read_text()
    letters = re.search(r'"([A-Z]+)"\.split', js).group(1)
    digits = re.search(r'"([0-9]+)"\.split', js).group(1)
    punct = re.search(r'\.concat\("(.*?)"\.split\(""\)\)\s*\n\s*\.concat\(CHIPS\)', js).group(1)
    punct = punct.encode().decode("unicode_escape").encode("latin-1").decode("utf-8")
    assert [" "] + list(letters) + list(digits) + list(punct) == data["sequence"]
    chips = re.findall(r'"\{([a-z]+)\}"', js)
    assert chips == data["chips"]


@pytest.mark.parametrize(
    ("ch", "expected"),
    [
        ("A", "A"),
        ("a", "A"),
        ("é", "E"),
        ("Ñ", "N"),
        ("°", "°"),
        ("\t", " "),
        ("ß", None),
        ("€", None),
    ],  # fmt: skip
)
def test_normalize_char(ch, expected):
    assert normalize_char(ch) == expected


def test_tokenize_text_chips_images_emoji():
    cells, unknown, images = tokenize("Hi {red} {img:my-cat} 🎉 👍🏽 🇨🇭 x€")
    assert cells == [
        "H", "I", " ", {"chip": "red"}, " ", {"img": "my-cat"}, " ", {"emoji": "🎉"}, " ",
        {"emoji": "👍🏽"}, " ", {"emoji": "🇨🇭"}, " ", "X", " ",
    ]  # fmt: skip
    assert unknown == ["€"]
    assert images == ["my-cat"]


def test_unknown_token_is_not_a_token():
    cells, unknown, _ = tokenize("{nope} {img:Bad Slug}")
    # braces are not in the flap set → blanks, reported
    assert "{" in unknown and "}" in unknown
    assert {"img": "Bad Slug"} not in cells


def test_rows_split_on_newline_and_wrap():
    lay = layout("DEPARTURES\nZRH 0715 BOARDING NOW PLEASE", 6, 22)
    assert lay.rows[0] == list("DEPARTURES")
    assert "".join(lay.rows[1]) == "ZRH 0715 BOARDING NOW"
    assert "".join(lay.rows[2]) == "PLEASE"
    assert lay.used == 10 + 21 + 6
    assert lay.capacity == 132
    assert not lay.overflow
    assert capacity_error(lay) is None


def test_long_word_is_cut():
    lay = layout("ABCDEFGHIJKLMNOPQRSTUVWXYZ", 6, 22)
    assert "".join(lay.rows[0]) == "ABCDEFGHIJKLMNOPQRSTUV"
    assert "".join(lay.rows[1]) == "WXYZ"


def test_overflow_is_an_error():
    lay = layout("\n".join(["X"] * 7), 6, 22)
    assert lay.overflow
    assert "7 rows" in capacity_error(lay)


def test_padded_rows_fill_the_grid():
    rows = padded_rows(layout("HI", 4, 16))
    assert len(rows) == 4 and all(len(r) == 16 for r in rows)
    assert rows[0][:3] == ["H", "I", " "]


def test_tokens_count_one_cell():
    lay = layout("{red}{img:a}🎉", 4, 16)
    assert lay.used == 3


BANNER = {"banner": {"w": 9, "h": 1, "fit": "contain", "ar": 6.405}}
LOGO = {"logo": {"w": 4, "h": 2, "fit": "cover", "ar": None}}


def part(slug, size, x, y):
    cell = {"img": slug, "w": size["w"], "h": size["h"], "x": x, "y": y, "fit": size["fit"]}
    if size["ar"]:
        cell["ar"] = size["ar"]
    return cell


def test_block_wraps_as_a_word_and_is_never_cut():
    lay = layout("HELLO WORLD {img:banner} BYE", 6, 22, BANNER)
    # HELLO WORLD = 11, + space + 9 = 21 fits; " BYE" does not → BYE wraps
    assert len(lay.rows) == 2
    assert lay.rows[0][12:21] == [part("banner", BANNER["banner"], x, 0) for x in range(9)]
    assert lay.rows[1] == ["B", "Y", "E"]
    lay = layout("HELLO WORLD AGAIN {img:banner}", 6, 22, BANNER)
    assert len(lay.rows) == 2 and len(lay.rows[1]) == 9, "the block moves whole to the next row"
    lay = layout("AB{img:banner}CD", 6, 16, BANNER)  # glued: a 13-wide word on a 16 board
    assert len(lay.rows) == 1 and lay.rows[0][0] == "A" and lay.rows[0][11] == "C"
    lay = layout("ABCDEFGH{img:banner}", 6, 16, BANNER)  # 17 wide: cut before the block
    assert [len(r) for r in lay.rows] == [8, 9]


def test_block_pushes_rows_down_and_used_counts_area():
    lay = layout("HI {img:logo} THERE\nNEXT", 6, 22, LOGO)
    assert lay.rows[0][:3] == ["H", "I", " "]
    assert lay.rows[0][3:7] == [part("logo", LOGO["logo"], x, 0) for x in range(4)]
    assert lay.rows[0][7:] == [" ", "T", "H", "E", "R", "E"]
    assert lay.rows[1] == [" ", " ", " "] + [part("logo", LOGO["logo"], x, 1) for x in range(4)]
    assert lay.rows[2] == ["N", "E", "X", "T"]
    assert lay.used == 2 + 1 + 4 * 2 + 1 + 5 + 4
    assert capacity_error(lay) is None


def test_block_wider_or_taller_than_the_board_is_refused_and_clamped():
    lay = layout("{img:banner}", 6, 8, BANNER)
    assert "9×1" in capacity_error(lay) and "8 columns" in capacity_error(lay)
    assert len(lay.rows[0]) == 8, "clamped so the board never breaks"
    tall = {"tower": {"w": 1, "h": 5, "fit": "contain", "ar": None}}
    lay = layout("{img:tower}", 4, 16, tall)
    assert "1×5" in capacity_error(lay) and "4 rows" in capacity_error(lay)
    assert len(lay.rows) == 4


def test_inline_override_at_wxh():
    lay = layout("{img:banner@3x2}", 6, 22, BANNER)
    assert lay.rows[0][0]["w"] == 3 and lay.rows[0][0]["h"] == 2 and lay.rows[0][0]["ar"] == 6.405
    assert len(lay.rows) == 2 and lay.used == 6
    lay = layout("{img:unknown@2x1}", 6, 22, {})  # no sidecar: the override still makes a block
    assert lay.rows[0] == [
        {"img": "unknown", "w": 2, "h": 1, "fit": "contain", "x": 0, "y": 0},
        {"img": "unknown", "w": 2, "h": 1, "fit": "contain", "x": 1, "y": 0},
    ]
    assert lay.images == ["unknown"]
    lay = layout("{img:banner@99x99}", 10, 36, BANNER)
    assert lay.rows[0][0]["w"] == 36 and lay.rows[0][0]["h"] == 10, "clamped to the biggest board"
    cells, _, _ = tokenize("{img:a@3x}")  # not a token
    assert {"img": "a"} not in cells


def test_padded_rows_cut_a_block_at_the_edge():
    lay = layout("X\nY\nZ\nW\nV\n{img:logo}", 6, 22, LOGO)
    rows = padded_rows(lay)
    assert len(rows) == 6 and rows[5][0]["y"] == 0 and all(len(r) == 22 for r in rows)


def test_legacy_picture_is_one_bare_cell():
    lay = layout("{img:old} HI", 6, 22, {})
    assert lay.rows[0] == [{"img": "old"}, " ", "H", "I"] and lay.used == 4


def test_solid_block_marks_every_part():
    """A picture drawn whole (`solid`, e.g. a QR code) says so on every part, so the board can lay
    one overlay over the block; a sliced picture carries no flag at all."""
    qr = {"menu": {"w": 4, "h": 3, "fit": "contain", "ar": 1.0, "solid": True, "qr": True}}
    rows = layout("{img:menu}", 6, 22, qr).rows
    parts = [c for row in rows for c in row if isinstance(c, dict)]
    assert len(parts) == 12
    assert all(c["solid"] is True and c["qr"] is True for c in parts)
    assert parts[0] == {
        "img": "menu",
        "w": 4,
        "h": 3,
        "fit": "contain",
        "ar": 1.0,
        "solid": True,
        "qr": True,
        "x": 0,
        "y": 0,
    }
    plain = {"menu": {**qr["menu"], "solid": False, "qr": False}}
    assert all(
        "solid" not in c and "qr" not in c
        for row in layout("{img:menu}", 6, 22, plain).rows
        for c in row
        if isinstance(c, dict)
    )
