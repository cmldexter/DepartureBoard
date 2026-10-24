"""The header reader: four formats, and garbage → None."""

import struct

import pytest

from app.services.imagesize import dimensions

PNG = (
    b"\x89PNG\r\n\x1a\n"
    + struct.pack(">I", 13)
    + b"IHDR"
    + struct.pack(">IIBBBBB", 743, 116, 8, 6, 0, 0, 0)
)
GIF = b"GIF89a" + struct.pack("<HH", 320, 50) + b"\x00" * 4
JPEG = (
    b"\xff\xd8"
    + b"\xff\xe0"
    + struct.pack(">H", 16)
    + b"JFIF\x00"
    + b"\x00" * 9  # APP0
    + b"\xff\xc0"
    + struct.pack(">H", 17)
    + b"\x08"
    + struct.pack(">HH", 116, 743)
    + b"\x03"
    + b"\x00" * 9  # SOF0: h, w
)
JPEG_PROGRESSIVE = JPEG.replace(b"\xff\xc0", b"\xff\xc2")
WEBP_VP8X = (
    b"RIFF"
    + b"\x00" * 4
    + b"WEBP"
    + b"VP8X"
    + struct.pack("<I", 10)
    + b"\x00" * 4
    + (742).to_bytes(3, "little")
    + (115).to_bytes(3, "little")
)
WEBP_VP8L = (
    b"RIFF"
    + b"\x00" * 4
    + b"WEBP"
    + b"VP8L"
    + struct.pack("<I", 5)
    + b"\x2f"
    + struct.pack("<I", (742) | (115 << 14))
)
WEBP_VP8 = (
    b"RIFF"
    + b"\x00" * 4
    + b"WEBP"
    + b"VP8 "
    + struct.pack("<I", 10)
    + b"\x00" * 3
    + b"\x9d\x01\x2a"
    + struct.pack("<HH", 743, 116)
)


@pytest.mark.parametrize(
    ("name", "data", "expected"),
    [
        ("png", PNG, (743, 116)),
        ("gif", GIF, (320, 50)),
        ("jpeg", JPEG, (743, 116)),
        ("jpeg progressive", JPEG_PROGRESSIVE, (743, 116)),
        ("webp vp8x", WEBP_VP8X, (743, 116)),
        ("webp vp8l", WEBP_VP8L, (743, 116)),
        ("webp vp8", WEBP_VP8, (743, 116)),
        ("garbage", b"not an image at all", None),
        ("truncated png", PNG[:20], None),
        ("empty", b"", None),
        ("jpeg without a frame", b"\xff\xd8\xff\xda\x00\x02", None),
    ],
)
def test_dimensions(name, data, expected):
    assert dimensions(data) == expected, name
