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
