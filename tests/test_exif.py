"""A phone's metadata does not reach the TV: the stripper drops it and the picture still reads."""

import struct
import zlib

from app.services.exif import strip
from app.services.imagesize import dimensions


def _seg(marker: int, body: bytes) -> bytes:
    return bytes([0xFF, marker]) + struct.pack(">H", len(body) + 2) + body


EXIF = _seg(0xE1, b"Exif\x00\x00" + b"II*\x00" + b"\x08\x00\x00\x00" + b"GPS" * 10)
XMP = _seg(0xE1, b"http://ns.adobe.com/xap/1.0/\x00<x:xmpmeta/>")
ICC = _seg(0xE2, b"ICC_PROFILE\x00" + b"\x00" * 20)
COMMENT = _seg(0xFE, b"taken at home")
JFIF = _seg(0xE0, b"JFIF\x00\x01\x02\x00\x00\x01\x00\x01\x00\x00")
ADOBE = _seg(0xEE, b"Adobe\x00" + b"\x00" * 6)
SOF0 = _seg(0xC0, b"\x08" + struct.pack(">HH", 116, 743) + b"\x03" + b"\x00" * 9)
SCAN = (
    b"\xff\xda"
    + struct.pack(">H", 8)
    + b"\x01\x01\x00\x00\x3f\x00"
    + b"\x12\x34\xff\x00\x56"
    + b"\xff\xd9"
)
JPEG = b"\xff\xd8" + JFIF + EXIF + XMP + ICC + COMMENT + ADOBE + SOF0 + SCAN


def test_jpeg_loses_exif_xmp_icc_and_comments_but_keeps_the_picture():
    out = strip(JPEG, "image/jpeg")
    assert out == b"\xff\xd8" + JFIF + ADOBE + SOF0 + SCAN
    assert b"GPS" not in out and b"xmpmeta" not in out and b"taken at home" not in out
    assert dimensions(out) == (743, 116), "the frame header is intact"
    assert out.endswith(b"\xff\xd9") and b"\xff\x00" in out, "the scan is copied verbatim"


def test_jpeg_without_metadata_is_unchanged():
    plain = b"\xff\xd8" + JFIF + SOF0 + SCAN
    assert strip(plain, "image/jpeg") == plain


def _chunk(kind: bytes, body: bytes) -> bytes:
    return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))


IHDR = _chunk(b"IHDR", struct.pack(">IIBBBBB", 4, 2, 8, 0, 0, 0, 0))
IDAT = _chunk(b"IDAT", zlib.compress(b"\x00" * 10))
IEND = _chunk(b"IEND", b"")
PNG = (
    b"\x89PNG\r\n\x1a\n"
    + IHDR
    + _chunk(b"tEXt", b"Comment\x00shot at 51.5N 0.1W")
    + _chunk(b"iTXt", b"XML:com.adobe.xmp\x00\x00\x00\x00\x00<x:xmpmeta/>")
    + _chunk(b"zTXt", b"k\x00\x00" + zlib.compress(b"v"))
    + _chunk(b"eXIf", b"II*\x00" + b"\x00" * 8)
    + IDAT
    + IEND
)


def test_png_loses_text_and_exif_chunks_but_keeps_the_picture():
    out = strip(PNG, "image/png")
    assert out == b"\x89PNG\r\n\x1a\n" + IHDR + IDAT + IEND
    assert b"51.5N" not in out and dimensions(out) == (4, 2)


def _riff(kind: bytes, body: bytes) -> bytes:
    return kind + struct.pack("<I", len(body)) + body + (b"\x00" if len(body) & 1 else b"")


VP8X = _riff(
    b"VP8X",
    bytes([0x08 | 0x04 | 0x10])
    + b"\x00\x00\x00"
    + (3).to_bytes(3, "little")
    + (1).to_bytes(3, "little"),
)
VP8 = _riff(b"VP8 ", b"\x00" * 6 + b"\x9d\x01\x2a" + struct.pack("<HH", 4, 2) + b"\x00" * 5)
WEBP = (
    b"RIFF"
    + struct.pack("<I", 4 + len(VP8X) + 16 + len(VP8) + 14)
    + b"WEBP"
    + VP8X
    + _riff(b"EXIF", b"II*\x00gps")
    + VP8
    + _riff(b"XMP ", b"<x/>x")
)


def test_webp_loses_exif_and_xmp_chunks_and_forgets_their_flags():
    out = strip(WEBP, "image/webp")
    assert b"EXIF" not in out and b"XMP " not in out and b"gps" not in out
    assert out[12:16] == b"VP8X" and out[20] & 0x0C == 0 and out[20] & 0x10, (
        "flags: EXIF and XMP cleared, alpha kept"
    )
    assert struct.unpack("<I", out[4:8])[0] == len(out) - 8, "the RIFF size is right"
    assert dimensions(out) == (4, 2)


def test_other_types_pass_through():
    assert strip(b"GIF89a" + b"\x00" * 10, "image/gif") == b"GIF89a" + b"\x00" * 10
    assert strip(b"nonsense", "image/jpeg") == b"nonsense"
