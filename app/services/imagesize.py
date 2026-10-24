"""Pixel size from an image's header — PNG, GIF, JPEG, WebP — without decoding it.

Enough to suggest how many flap cells a picture wants. Anything it does not understand is None,
and the picture still uploads.
"""

import struct


def dimensions(data: bytes) -> tuple[int, int] | None:
    """(width, height) in pixels, or None when the header is not one we read."""
    try:
        if data[:8] == b"\x89PNG\r\n\x1a\n" and data[12:16] == b"IHDR":
            w, h = struct.unpack(">II", data[16:24])
            return (w, h) if w and h else None
        if data[:6] in (b"GIF87a", b"GIF89a"):
            w, h = struct.unpack("<HH", data[6:10])
            return (w, h) if w and h else None
        if data[:2] == b"\xff\xd8":
            return _jpeg(data)
        if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
            return _webp(data)
    except (struct.error, IndexError):
        return None
    return None


def _jpeg(data: bytes) -> tuple[int, int] | None:
    """Walk the segments to the first start-of-frame (SOF0–SOF15, except DHT/JPG/DAC)."""
    i = 2
    n = len(data)
    while i + 9 < n:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        if marker == 0xFF:
            i += 1
            continue
        length = struct.unpack(">H", data[i + 2 : i + 4])[0]
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            h, w = struct.unpack(">HH", data[i + 5 : i + 9])
            return (w, h) if w and h else None
        if marker == 0xDA:  # start of scan: no frame header before the data → give up
            return None
        i += 2 + length
    return None


def _webp(data: bytes) -> tuple[int, int] | None:
    chunk = data[12:16]
    if chunk == b"VP8X":
        w = 1 + int.from_bytes(data[24:27], "little")
        h = 1 + int.from_bytes(data[27:30], "little")
        return (w, h)
    if chunk == b"VP8 ":
        w, h = struct.unpack("<HH", data[26:30])
        return (w & 0x3FFF, h & 0x3FFF) or None
    if chunk == b"VP8L":
        bits = int.from_bytes(data[21:25], "little")
        return (1 + (bits & 0x3FFF), 1 + ((bits >> 14) & 0x3FFF))
    return None
